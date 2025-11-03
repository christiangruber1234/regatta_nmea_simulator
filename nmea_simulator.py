'''
NMEA 0183 Simulator
===================
This module simulates NMEA 0183 data for GPS and wind instruments, sending it over UDP to a specified host and port.
It generates GPRMC, GPGGA, GPVTG, WIMWD, and WIMWV sentences with realistic but simulated data.
The simulation includes random variations in position, speed, course, wind speed, and wind direction.

Now supports programmatic control via the NMEASimulator class (start/stop) and CLI arguments for standalone use.

Author: Christian Heiling
Revision History:
- v1.0: Initial version
- v1.1: Added wind instrument simulation (allows to enable/disable wind data)
- v2.0: Refactor into NMEASimulator class with start/stop and configurable starting lat/lon/datetime

'''

import socket
import time
import math
import random
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict
import argparse

# --- Configuration ---
TARGET_HOST = '127.0.0.1'  # IP address to send NMEA data to (localhost)
TARGET_PORT = 10110        # Port to send NMEA data to (must match listener)
SEND_INTERVAL = 1.0        # Seconds between sending NMEA sentences
WIND_INSTRUMENTS_ENABLED = False # Set to False to simulate wind instruments being disconnected

# --- Simulation Parameters ---
# Initial values
DEFAULT_LAT = 47.0707   # Decimal degrees (e.g., Graz, Austria)
DEFAULT_LON = 15.4395   # Decimal degrees
DEFAULT_SOG = 5.0       # Speed Over Ground in knots
DEFAULT_COG = 45.0      # Course Over Ground in degrees True
DEFAULT_TWS = 10.0      # True Wind Speed in knots
DEFAULT_TWD = 270.0     # True Wind Direction in degrees True (from North)
DEFAULT_MAGVAR = -2.5   # Magnetic variation, degrees West (-) or East (+)

# --- Helper Functions ---

def calculate_nmea_checksum(sentence_body: str) -> str:
    """Calculates the NMEA checksum for a sentence body (without '$' or '*')"""
    checksum = 0
    for char in sentence_body:
        checksum ^= ord(char)
    return f"{checksum:02X}" # Return as two-digit hex string

def format_nmea_lat(lat_decimal: float) -> str:
    """Converts decimal latitude to NMEA format (ddmm.mmmm,H)"""
    indicator = 'N' if lat_decimal >= 0 else 'S'
    lat_abs = abs(lat_decimal)
    degrees = int(lat_abs)
    minutes = (lat_abs - degrees) * 60
    return f"{degrees:02d}{minutes:07.4f},{indicator}" # ddmm.mmmm

def format_nmea_lon(lon_decimal: float) -> str:
    """Converts decimal longitude to NMEA format (dddmm.mmmm,H)"""
    indicator = 'E' if lon_decimal >= 0 else 'W'
    lon_abs = abs(lon_decimal)
    degrees = int(lon_abs)
    minutes = (lon_abs - degrees) * 60
    return f"{degrees:03d}{minutes:07.4f},{indicator}" # dddmm.mmmm

# --- NMEA Sentence Generators ---

def create_gprmc(utc_time, lat, lon, sog_knots, cog_degrees, mag_var_deg) -> str:
    """Creates a GPRMC sentence."""
    # $GPRMC,time,status,lat,N/S,lon,E/W,sog,cog,date,mag_var,mag_var_dir*CS
    # Example: $GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A
    
    time_str = utc_time.strftime("%H%M%S.%f")[:9] # HHMMSS.ss
    date_str = utc_time.strftime("%d%m%y")
    
    lat_nmea = format_nmea_lat(lat)
    lon_nmea = format_nmea_lon(lon)
    
    sog_str = f"{sog_knots:.1f}"
    cog_str = f"{cog_degrees:.1f}"
    
    mag_var_abs = abs(mag_var_deg)
    mag_var_dir = 'E' if mag_var_deg >= 0 else 'W'
    mag_var_str = f"{mag_var_abs:.1f},{mag_var_dir}"
    
    # Status: A=Active, V=Void
    status = 'A'
    
    body = f"GPRMC,{time_str},{status},{lat_nmea},{lon_nmea},{sog_str},{cog_str},{date_str},{mag_var_str}"
    checksum = calculate_nmea_checksum(body)
    return f"${body}*{checksum}\r\n"

def create_gpgga(utc_time, lat, lon, num_sats=8, hdop=1.5, altitude_m=10.0) -> str:
    """Creates a GPGGA sentence."""
    # $GPGGA,time,lat,N/S,lon,E/W,fix_quality,num_sats,hdop,altitude,M,geoid_sep,M,age_dgps,dgps_id*CS
    # Example: $GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47

    time_str = utc_time.strftime("%H%M%S.%f")[:9] # HHMMSS.ss
    lat_nmea = format_nmea_lat(lat)
    lon_nmea = format_nmea_lon(lon)
    
    fix_quality = "1" # 1 = GPS fix
    sats_str = f"{num_sats:02d}"
    hdop_str = f"{hdop:.1f}"
    alt_str = f"{altitude_m:.1f}"
    geoid_sep_str = "0.0" # Geoidal separation (dummy)
    
    body = f"GPGGA,{time_str},{lat_nmea},{lon_nmea},{fix_quality},{sats_str},{hdop_str},{alt_str},M,{geoid_sep_str},M,,"
    checksum = calculate_nmea_checksum(body)
    return f"${body}*{checksum}\r\n"

def create_gpvtg(cog_true_deg, cog_mag_deg, sog_knots, sog_kmh) -> str:
    """Creates a GPVTG sentence."""
    # $GPVTG,cog_true,T,cog_mag,M,sog_knots,N,sog_kmh,K,mode*CS
    # Example: $GPVTG,054.7,T,,M,005.5,N,010.2,K*48 (Magnetic course often empty if not available)

    cog_t_str = f"{cog_true_deg:.1f}"
    cog_m_str = f"{cog_mag_deg:.1f}" if cog_mag_deg is not None else ""
    sog_n_str = f"{sog_knots:.1f}"
    sog_k_str = f"{sog_kmh:.1f}"
    mode = "A" # A=Autonomous, D=Differential, E=Estimated, N=Not valid, S=Simulator

    body = f"GPVTG,{cog_t_str},T,{cog_m_str},M,{sog_n_str},N,{sog_k_str},K,{mode}"
    checksum = calculate_nmea_checksum(body)
    return f"${body}*{checksum}\r\n"

def create_wimwd(twd_true_deg, twd_mag_deg, tws_knots, tws_mps) -> str:
    """Creates a WIMWD sentence (True Wind Direction and Speed)."""
    # $WIMWD,dir_true,T,dir_mag,M,speed_knots,N,speed_mps,M*CS
    # Example: $WIMWD,095.0,T,092.5,M,010.5,N,005.4,M*57

    twd_t_str = f"{twd_true_deg:.1f}"
    twd_m_str = f"{twd_mag_deg:.1f}"
    tws_n_str = f"{tws_knots:.1f}"
    tws_m_str = f"{tws_mps:.1f}"

    body = f"WIMWD,{twd_t_str},T,{twd_m_str},M,{tws_n_str},N,{tws_m_str},M"
    checksum = calculate_nmea_checksum(body)
    return f"${body}*{checksum}\r\n"

def create_wimwv_true(twa_deg, tws_knots) -> str:
    """Creates a WIMWV sentence for True Wind (angle relative to bow, speed)."""
    # $WIMWV,wind_angle,reference(R/T),wind_speed,unit(N/K/M),status(A/V)*CS
    # Example for True Wind Angle (TWA) and True Wind Speed (TWS):
    # $WIMWV,110.0,T,12.5,N,A*CS (Here 'T' means the angle and speed are True, not that angle is to True North)
    # This interpretation of MWV for TWA/TWS can vary. Some systems use MWD for TWD/TWS.
    # We'll assume 'T' means the data is True, and the angle is relative to the bow.

    angle_str = f"{abs(twa_deg):.1f}" # Angle is often positive, direction implied by context or other sentences
    ref = "T" # T for True wind data
    speed_str = f"{tws_knots:.1f}"
    unit = "N" # N for knots
    status = "A" # A for Active

    body = f"WIMWV,{angle_str},{ref},{speed_str},{unit},{status}"
    checksum = calculate_nmea_checksum(body)
    return f"${body}*{checksum}\r\n"

def create_wimwv_apparent(awa_deg, aws_knots) -> str:
    """Creates a WIMWV sentence for Apparent Wind (angle relative to bow, speed)."""
    # $WIMWV,wind_angle,R,wind_speed,N,A*CS
    angle_str = f"{abs(awa_deg):.1f}"
    ref = "R" # R for Relative (Apparent) wind data
    speed_str = f"{aws_knots:.1f}"
    unit = "N" # N for knots
    status = "A" # A for Active

    body = f"WIMWV,{angle_str},{ref},{speed_str},{unit},{status}"
    checksum = calculate_nmea_checksum(body)
    return f"${body}*{checksum}\r\n"

def create_gpgsa(mode: str, fix_type: int, sv_ids: List[int], pdop: float, hdop: float, vdop: float) -> str:
    """Creates a GPGSA sentence (DOP and active satellites).
    mode: 'M' manual, 'A' automatic
    fix_type: 1=no fix, 2=2D, 3=3D
    sv_ids: up to 12 PRN numbers used for fix
    """
    # Pad/trim to 12 SV IDs
    sv_fields = [str(prn).zfill(2) for prn in sv_ids[:12]]
    while len(sv_fields) < 12:
        sv_fields.append("")
    body = f"GPGSA,{mode},{fix_type}," + ",".join(sv_fields) + f",{pdop:.1f},{hdop:.1f},{vdop:.1f}"
    checksum = calculate_nmea_checksum(body)
    return f"${body}*{checksum}\r\n"

def create_gpgsv(satellites: List[Dict]) -> List[str]:
    """Creates one or more GPGSV sentences (satellites in view).
    satellites: list of dicts with keys prn, elev, az, snr
    Returns list of sentence strings.
    """
    sentences = []
    total_sats = len(satellites)
    sats_per_msg = 4
    total_msgs = max(1, (total_sats + sats_per_msg - 1) // sats_per_msg)
    for i in range(total_msgs):
        msg_num = i + 1
        chunk = satellites[i*sats_per_msg:(i+1)*sats_per_msg]
        fields = [f"GPGSV,{total_msgs},{msg_num},{total_sats:02d}"]
        for sat in chunk:
            prn = int(sat.get('prn', 0))
            elev = int(sat.get('elev', 0))
            az = int(sat.get('az', 0))
            snr = int(sat.get('snr', 0))
            fields.extend([str(prn).zfill(2), str(elev), str(az), str(snr)])
        body = ",".join(fields)
        checksum = calculate_nmea_checksum(body)
        sentences.append(f"${body}*{checksum}\r\n")
    return sentences


class NMEASimulator:
    """A controllable NMEA 0183 UDP simulator running in a background thread."""

    def __init__(
        self,
        host: str = TARGET_HOST,
        port: int = TARGET_PORT,
        interval: float = SEND_INTERVAL,
        wind_enabled: bool = WIND_INSTRUMENTS_ENABLED,
        start_lat: float = DEFAULT_LAT,
        start_lon: float = DEFAULT_LON,
        sog_knots: float = DEFAULT_SOG,
        cog_degrees: float = DEFAULT_COG,
        tws_knots: float = DEFAULT_TWS,
        twd_degrees: float = DEFAULT_TWD,
        mag_variation: float = DEFAULT_MAGVAR,
        start_datetime: Optional[datetime] = None,
    ) -> None:
        self.host = host
        self.port = int(port)
        self.interval = float(interval)
        self.wind_enabled = bool(wind_enabled)

        # Simulation state
        self.lat = float(start_lat)
        self.lon = float(start_lon)
        self.sog = float(sog_knots)
        self.cog = float(cog_degrees) % 360
        self.tws = float(tws_knots)
        self.twd = float(twd_degrees) % 360
        self.magvar = float(mag_variation)
        self.sim_time = start_datetime.replace(tzinfo=timezone.utc) if start_datetime else None

        # Runtime control
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._sock: Optional[socket.socket] = None
        self._last_status = {}

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        if not self.is_running():
            return
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=timeout)
        self._thread = None
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    def restart(self, **kwargs) -> None:
        self.stop()
        with self._lock:
            for k, v in kwargs.items():
                if hasattr(self, k):
                    setattr(self, k, v)
        self.start()

    def status(self) -> dict:
        with self._lock:
            st = {
                "running": self.is_running(),
                "host": self.host,
                "port": self.port,
                "interval": self.interval,
                "wind_enabled": self.wind_enabled,
                "lat": self.lat,
                "lon": self.lon,
                "sog": self.sog,
                "cog": self.cog,
                "tws": self.tws,
                "twd": self.twd,
                "magvar": self.magvar,
                "sim_time": self.sim_time.isoformat() if self.sim_time else None,
                "gnss": self._last_status.get("gnss") if isinstance(self._last_status, dict) else None,
            }
        return st

    # Internal helpers
    def _run_loop(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        print(f"NMEA Simulator started. Sending data to {self.host}:{self.port} every {self.interval}s.")
        try:
            while not self._stop_event.is_set():
                with self._lock:
                    # Simulation time: use provided start time and advance, else real UTC
                    if self.sim_time is None:
                        current_utc_time = datetime.utcnow().replace(tzinfo=timezone.utc)
                    else:
                        current_utc_time = self.sim_time
                        self.sim_time = self.sim_time + timedelta(seconds=self.interval)

                    # Update simulated kinematics
                    dt_hours = self.interval / 3600.0
                    dist_nm = self.sog * dt_hours

                    rad_lat = math.radians(self.lat)
                    rad_cog = math.radians(self.cog)

                    self.lat += (dist_nm / 60.0) * math.cos(rad_cog)
                    if abs(self.lat) > 90:
                        self.lat = math.copysign(90, self.lat)

                    if abs(self.lat) < 89.99:
                        self.lon += (dist_nm / (60.0 * math.cos(rad_lat))) * math.sin(rad_cog)
                    if self.lon > 180:
                        self.lon -= 360
                    if self.lon < -180:
                        self.lon += 360

                    # Random walk adjustments
                    self.sog = max(0, min(self.sog + random.uniform(-0.2, 0.2), 15.0))
                    self.cog = (self.cog + random.uniform(-2.0, 2.0)) % 360
                    self.tws = max(0, min(self.tws + random.uniform(-0.3, 0.3), 30.0))
                    self.twd = (self.twd + random.uniform(-3.0, 3.0)) % 360

                    # Derived values
                    cog_mag = (self.cog - self.magvar + 360) % 360
                    sog_kmh = self.sog * 1.852
                    twd_mag = (self.twd - self.magvar + 360) % 360
                    tws_mps = self.tws * 0.514444

                    # TWA
                    twa = self.twd - self.cog
                    while twa > 180:
                        twa -= 360
                    while twa <= -180:
                        twa += 360

                    awa = twa * random.uniform(0.8, 1.1)
                    aws = self.tws * random.uniform(0.9, 1.5)
                    if self.sog < 1:
                        awa = twa
                        aws = self.tws

                    # Generate sentences
                    # GNSS simulation (GSA/GSV)
                    sats_in_view = random.randint(8, 14)
                    prns = random.sample(range(1, 33), sats_in_view)
                    sats_used_count = min(random.randint(6, 12), sats_in_view)
                    used_prns = set(prns[:sats_used_count])
                    satellites = []
                    for prn in prns:
                        satellites.append({
                            "prn": prn,
                            "elev": random.randint(5, 85),
                            "az": random.randint(0, 359),
                            "snr": random.randint(20, 48),
                            "used": prn in used_prns,
                        })
                    pdop = round(random.uniform(1.3, 3.5), 1)
                    hdop = round(random.uniform(0.7, 2.5), 1)
                    vdop = round(random.uniform(1.0, 3.0), 1)

                    nmea_gprmc = create_gprmc(current_utc_time, self.lat, self.lon, self.sog, self.cog, self.magvar)
                    nmea_gpgga = create_gpgga(current_utc_time, self.lat, self.lon, num_sats=sats_used_count, hdop=hdop)
                    nmea_gpvtg = create_gpvtg(self.cog, cog_mag, self.sog, sog_kmh)
                    # Build GSA and GSV
                    gsa = create_gpgsa('A', 3, list(used_prns), pdop, hdop, vdop)
                    gsv_list = create_gpgsv(satellites)

                    full_nmea_packet = nmea_gprmc + nmea_gpgga + nmea_gpvtg + gsa + "".join(gsv_list)
                    if self.wind_enabled:
                        nmea_wimwd = create_wimwd(self.twd, twd_mag, self.tws, tws_mps)
                        nmea_wimwv_true = create_wimwv_true(twa, self.tws)
                        nmea_wimwv_apparent = create_wimwv_apparent(awa, aws)
                        full_nmea_packet += nmea_wimwd + nmea_wimwv_true + nmea_wimwv_apparent

                    # Update last status for API consumers
                    self._last_status = {
                        "gnss": {
                            "sats_in_view": sats_in_view,
                            "sats_used": sats_used_count,
                            "pdop": pdop,
                            "hdop": hdop,
                            "vdop": vdop,
                            "satellites": satellites,
                        }
                    }

                # Send outside the lock
                self._sock.sendto(full_nmea_packet.encode('ascii'), (self.host, self.port))

                wind_info = (
                    f"TWS={self.tws:.1f}kn, TWD={self.twd:.0f}°, TWA={twa:.0f}°"
                    if self.wind_enabled
                    else "TWS=---, TWD=---, TWA=---"
                )
                print(
                    f"Sent at {current_utc_time.strftime('%H:%M:%S')}: "
                    f"Lat={self.lat:.4f}, Lon={self.lon:.4f}, SOG={self.sog:.1f}kn, COG={self.cog:.0f}°, "
                    f"{wind_info}"
                )

                time.sleep(self.interval)
        except Exception as e:
            print(f"**ERR: Simulator error: {e}")
        finally:
            try:
                if self._sock:
                    self._sock.close()
            finally:
                self._sock = None
                print("Simulator socket closed.")


def run_simulator(host, port, interval, **kwargs):
    sim = NMEASimulator(host=host, port=port, interval=interval, **kwargs)
    sim.start()
    try:
        # Keep main thread alive until Ctrl+C
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nSimulator stopped by user.")
    finally:
        sim.stop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NMEA 0183 UDP Simulator")
    parser.add_argument("--host", default=TARGET_HOST, help="Target host")
    parser.add_argument("--port", type=int, default=TARGET_PORT, help="Target UDP port")
    parser.add_argument("--interval", type=float, default=SEND_INTERVAL, help="Send interval seconds")
    parser.add_argument("--wind", action="store_true", help="Enable wind sentences")
    parser.add_argument("--lat", type=float, default=DEFAULT_LAT, help="Starting latitude")
    parser.add_argument("--lon", type=float, default=DEFAULT_LON, help="Starting longitude")
    parser.add_argument("--sog", type=float, default=DEFAULT_SOG, help="Initial SOG (knots)")
    parser.add_argument("--cog", type=float, default=DEFAULT_COG, help="Initial COG (deg true)")
    parser.add_argument("--tws", type=float, default=DEFAULT_TWS, help="Initial TWS (knots)")
    parser.add_argument("--twd", type=float, default=DEFAULT_TWD, help="Initial TWD (deg true)")
    parser.add_argument("--magvar", type=float, default=DEFAULT_MAGVAR, help="Magnetic variation (deg, E=+ / W=-)")
    parser.add_argument(
        "--start-datetime",
        type=str,
        default=None,
        help="Start datetime in ISO format (UTC). If omitted, uses real current UTC for each sentence.",
    )

    args = parser.parse_args()
    start_dt = None
    if args.start_datetime:
        try:
            # Accept both with and without timezone; assume UTC if none
            start_dt = datetime.fromisoformat(args.start_datetime)
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            else:
                start_dt = start_dt.astimezone(timezone.utc)
        except Exception as e:
            print(f"Invalid --start-datetime: {e}. Falling back to real-time UTC.")
            start_dt = None

    print(f"WIND_INSTRUMENTS_ENABLED = {args.wind}")
    run_simulator(
        args.host,
        args.port,
        args.interval,
        wind_enabled=args.wind,
        start_lat=args.lat,
        start_lon=args.lon,
        sog_knots=args.sog,
        cog_degrees=args.cog,
        tws_knots=args.tws,
        twd_degrees=args.twd,
        mag_variation=args.magvar,
        start_datetime=start_dt,
    )
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
from typing import Optional, List, Dict, Tuple, Deque
from collections import deque
import argparse
import os

# --- Configuration ---
TARGET_HOST = '127.0.0.1'  # IP address to send NMEA data to (localhost)
TARGET_PORT = 10110        # Port to send NMEA data to (must match listener)
SEND_INTERVAL = 1.0        # Seconds between sending NMEA sentences
WIND_INSTRUMENTS_ENABLED = True # Default to True; set to False to simulate wind instruments being disconnected

# --- Simulation Parameters ---
# Initial values
DEFAULT_LAT = 42.715769349296004   # Default starting latitude
DEFAULT_LON = 16.23217374761267    # Default starting longitude
DEFAULT_SOG = 5.0       # Speed Over Ground in knots
DEFAULT_COG = 185.0     # Course Over Ground in degrees True
DEFAULT_TWS = 10.0      # True Wind Speed in knots
DEFAULT_TWD = 270.0     # True Wind Direction in degrees True (from North)
DEFAULT_MAGVAR = -2.5   # Magnetic variation, degrees West (-) or East (+)
DEFAULT_TCP_PORT = 10111 # Default TCP server port for NMEA stream

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

# --- AIS Helpers (AIVDM Type 18 - Class B position) ---

def _pack_signed(value: int, bits: int) -> str:
    if value < 0:
        value = (1 << bits) + value
    return format(value, f"0{bits}b")[-bits:]

def _pack_unsigned(value: int, bits: int) -> str:
    return format(max(0, min(value, (1 << bits) - 1)), f"0{bits}b")

def _sixbit_to_payload(bits: str) -> Tuple[str, int]:
    # Pad to 6-bit boundary
    fill = (6 - (len(bits) % 6)) % 6
    if fill:
        bits += "0" * fill
    out_chars = []
    for i in range(0, len(bits), 6):
        val = int(bits[i:i+6], 2)
        val += 48
        if val > 87:
            val += 8
        out_chars.append(chr(val))
    return ("".join(out_chars), fill)

# AIS 6-bit text character set per ITU-R M.1371
_AIS_CHARSET = "@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_ !\"#$%&'()*+,-./0123456789:;<=>?"

def _ais_text_to_sixbit(text: str, width: int) -> str:
    """Encode ASCII text to AIS 6-bit field of fixed width (chars). Pads with '@'."""
    if text is None:
        text = ""
    s = str(text).upper()
    chars = []
    for ch in s:
        if ch in _AIS_CHARSET:
            chars.append(ch)
        else:
            chars.append(' ')
    chars = chars[:width]
    while len(chars) < width:
        chars.append('@')
    bits = ''.join(format(_AIS_CHARSET.index(c), '06b') for c in chars)
    return bits

def create_aivdm_type18(mmsi: int, lat: float, lon: float, sog_knots: float, cog_deg: float, heading_deg: float, ts_sec: int) -> str:
    # Build AIS message type 18 per ITU-R M.1371 with many fields defaulted
    # Scale values
    sog = int(round(max(0.0, min(sog_knots, 102.2)) * 10))  # 0.1 knot
    if sog > 1022:
        sog = 1022
    lon_i = int(round(lon * 600000))
    lat_i = int(round(lat * 600000))
    cog = int(round((cog_deg % 360.0) * 10))
    if cog == 3600:
        cog = 0
    hdg = int(round(heading_deg % 360.0))
    ts = max(0, min(int(ts_sec % 60), 59))

    bits = ""
    bits += _pack_unsigned(18, 6)     # Message ID
    bits += _pack_unsigned(0, 2)      # Repeat
    bits += _pack_unsigned(int(mmsi), 30)  # MMSI
    bits += _pack_unsigned(0, 8)      # reserved
    bits += _pack_unsigned(sog, 10)   # SOG 0.1 kn
    bits += _pack_unsigned(0, 1)      # Position accuracy
    bits += _pack_signed(lon_i, 28)   # Longitude
    bits += _pack_signed(lat_i, 27)   # Latitude
    bits += _pack_unsigned(cog, 12)   # COG 0.1 deg
    bits += _pack_unsigned(hdg if hdg <= 359 else 511, 9)  # True heading
    bits += _pack_unsigned(ts, 6)     # Timestamp seconds
    bits += _pack_unsigned(0, 2)      # reserved
    bits += _pack_unsigned(0, 1)      # CS unit flag / unit flag
    bits += _pack_unsigned(0, 1)      # display flag
    bits += _pack_unsigned(0, 1)      # DSC flag
    bits += _pack_unsigned(0, 1)      # band flag
    bits += _pack_unsigned(0, 1)      # msg 22 flag
    bits += _pack_unsigned(0, 1)      # mode flag
    bits += _pack_unsigned(0, 1)      # RAIM flag
    bits += _pack_unsigned(0, 1)      # Comm state selector (SOTDMA=0)
    bits += _pack_unsigned(0, 19)     # Comm state (dummy)

    payload, fill = _sixbit_to_payload(bits)
    body = f"AIVDM,1,1,,A,{payload},{fill}"
    cs = calculate_nmea_checksum(body)
    return f"!{body}*{cs}\r\n"

def create_aivdm_type24_part_a(mmsi: int, name: str) -> str:
    """AIS Class B static data report, Part A (vessel name)."""
    bits = ""
    bits += _pack_unsigned(24, 6)   # Message ID
    bits += _pack_unsigned(0, 2)    # Repeat
    bits += _pack_unsigned(int(mmsi), 30)  # MMSI
    bits += _pack_unsigned(0, 2)    # Part number = 0 (Part A)
    bits += _ais_text_to_sixbit(name or "Vessel", 20)  # Name (20 chars)
    payload, fill = _sixbit_to_payload(bits)
    body = f"AIVDM,1,1,,A,{payload},{fill}"
    cs = calculate_nmea_checksum(body)
    return f"!{body}*{cs}\r\n"

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
        ais_num_targets: int = 0,
        ais_max_cog_offset: float = 20.0,
        ais_max_sog_offset: float = 2.0,
        ais_distribution_radius_nm: float = 1.0,
        tcp_port: Optional[int] = DEFAULT_TCP_PORT,
        tcp_host: str = "0.0.0.0",
        gpx_track: Optional[List[Dict]] = None,
        gpx_start_fraction: Optional[float] = None,
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
        # GPX playback
        self._gpx_track = self._prepare_gpx(gpx_track)
        self._gpx_duration_s = None
        self._gpx_start_time = None
        self._gpx_end_time = None
        if self._gpx_track:
            self._gpx_start_time = self._gpx_track[0]["time"]
            self._gpx_end_time = self._gpx_track[-1]["time"]
            try:
                self._gpx_duration_s = max(0, int((self._gpx_end_time - self._gpx_start_time).total_seconds())) if (self._gpx_start_time and self._gpx_end_time) else None
            except Exception:
                self._gpx_duration_s = None
            # Initialize cursor for non-timestamped tracks based on fraction
            if (self._gpx_duration_s is None or self._gpx_start_time is None or self._gpx_end_time is None) and (gpx_start_fraction is not None):
                try:
                    f = max(0.0, min(1.0, float(gpx_start_fraction)))
                    idx = int(round(f * (len(self._gpx_track) - 1)))
                    idx = max(0, min(idx, len(self._gpx_track) - 2))
                    self._gpx_cursor = idx
                    self.lat = self._gpx_track[idx]["lat"]
                    self.lon = self._gpx_track[idx]["lon"]
                    nxt = self._gpx_track[idx+1]
                    self.cog = self._bearing_deg(self.lat, self.lon, nxt["lat"], nxt["lon"]) % 360
                except Exception:
                    pass

        # AIS state
        self.ais_num_targets = int(max(0, ais_num_targets))
        self.ais_max_cog_offset = float(max(0.0, ais_max_cog_offset))
        self.ais_max_sog_offset = float(max(0.0, ais_max_sog_offset))
        self.ais_targets: List[Dict] = []
        self.ais_distribution_radius_nm = float(max(0.0, ais_distribution_radius_nm))
        # Load skipper names before creating AIS targets (used by name generator)
        self._skipper_names = self._load_skippers()
        self._init_ais_targets()

        # Runtime control
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._sock: Optional[socket.socket] = None
        self._last_status = {}
        # Stream buffer of recent lines
        self._stream = deque(maxlen=200)
        # Last minute when Type 24 static messages were emitted
        self._last_ais24_minute = None
        # TCP server state
        self.tcp_port = int(tcp_port) if tcp_port else None
        self.tcp_host = str(tcp_host or "0.0.0.0")
        self._tcp_server_sock = None
        self._tcp_clients = []  # each: {sock, addr, port, connected_at}

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
            # Build GPX info/progress if applicable
            gpx_info = None
            if self._gpx_track:
                has_time = bool(self._gpx_start_time and self._gpx_end_time and all(p.get("time") is not None for p in self._gpx_track))
                gpx_info = {
                    "points": len(self._gpx_track),
                    "start_time": self._gpx_start_time.isoformat() if self._gpx_start_time else None,
                    "end_time": self._gpx_end_time.isoformat() if self._gpx_end_time else None,
                    "duration_s": self._gpx_duration_s,
                    "has_time": has_time,
                }
                # Progress
                prog = {"mode": "none"}
                if has_time and self.sim_time is not None and self._gpx_start_time is not None and self._gpx_duration_s is not None:
                    try:
                        off = int((self.sim_time - self._gpx_start_time).total_seconds())
                    except Exception:
                        off = 0
                    if off < 0:
                        off = 0
                    if self._gpx_duration_s is not None:
                        off = min(off, int(self._gpx_duration_s))
                    prog = {"mode": "time", "offset_s": off, "sim_time": self.sim_time.isoformat()}
                elif not has_time:
                    idx = int(getattr(self, "_gpx_cursor", 0))
                    total_pts = max(1, len(self._gpx_track) - 1)
                    frac = max(0.0, min(1.0, idx / float(total_pts)))
                    prog = {"mode": "index", "index": idx, "fraction": frac}
                gpx_info["progress"] = prog
            st = {
                "running": self.is_running(),
                "host": self.host,
                "port": self.port,
                "tcp_port": self.tcp_port,
                "tcp_host": getattr(self, "tcp_host", "0.0.0.0"),
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
                "ais": self._last_status.get("ais") if isinstance(self._last_status, dict) else None,
                "stream_size": len(self._stream),
                "tcp_clients": self._tcp_clients_summary() if self.tcp_port else [],
                "gpx_track_info": gpx_info,
            }
        return st

    # Internal helpers
    def _run_loop(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Initialize TCP server if requested
        if self.tcp_port:
            try:
                srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                bind_host = getattr(self, "tcp_host", "0.0.0.0") or "0.0.0.0"
                srv.bind((bind_host, int(self.tcp_port)))
                srv.listen(8)
                srv.setblocking(False)
                self._tcp_server_sock = srv
                print(f"TCP server listening on {bind_host}:{self.tcp_port}")
            except Exception as e:
                print(f"**ERR: Failed to start TCP server on {self.tcp_port}: {e}")
                self._tcp_server_sock = None
        print(f"NMEA Simulator started. Sending data to {self.host}:{self.port} every {self.interval}s.")
        try:
            while not self._stop_event.is_set():
                with self._lock:
                    # Accept new TCP clients (non-blocking)
                    if self._tcp_server_sock is not None:
                        while True:
                            try:
                                csock, caddr = self._tcp_server_sock.accept()
                                csock.setblocking(False)
                                self._tcp_clients.append({
                                    "sock": csock,
                                    "addr": caddr[0],
                                    "port": caddr[1],
                                    "connected_at": datetime.utcnow().isoformat() + "Z",
                                })
                                print(f"TCP client connected: {caddr[0]}:{caddr[1]}")
                            except (BlockingIOError, InterruptedError):
                                break
                            except Exception:
                                break
                    # Simulation time: use provided start time and advance, else real UTC
                    if self.sim_time is None:
                        current_utc_time = datetime.utcnow().replace(tzinfo=timezone.utc)
                    else:
                        current_utc_time = self.sim_time
                        self.sim_time = self.sim_time + timedelta(seconds=self.interval)

                    # Update simulated kinematics or follow GPX track
                    dt_hours = self.interval / 3600.0
                    if self._gpx_track and (self._gpx_start_time is not None):
                        self._update_from_gpx(current_utc_time)
                    else:
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

                    # AIS update and messages
                    self._update_ais_targets(dt_hours)
                    ais_msgs = self._build_ais_sentences(current_utc_time)

                    full_nmea_packet = nmea_gprmc + nmea_gpgga + nmea_gpvtg + gsa + "".join(gsv_list) + ais_msgs
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
                        },
                        "ais": {
                            "num_targets": self.ais_num_targets,
                            "targets": [
                                {
                                    "mmsi": t["mmsi"],
                                    "lat": t["lat"],
                                    "lon": t["lon"],
                                    "sog": t["sog"],
                                    "cog": t["cog"],
                                    "name": t.get("name"),
                                    "display_name": f"{t.get('name') or 'Vessel'} (SOG {t['sog']:.1f} kn, COG {int(round(t['cog'])) % 360:03d}°)",
                                }
                                for t in self.ais_targets
                            ],
                        },
                    }

                # Send outside the lock
                self._sock.sendto(full_nmea_packet.encode('ascii'), (self.host, self.port))
                # Broadcast to TCP clients
                if self._tcp_clients:
                    dead = []
                    data = full_nmea_packet.encode('ascii')
                    for c in list(self._tcp_clients):
                        s = c.get("sock")
                        try:
                            if s:
                                s.sendall(data)
                        except Exception:
                            dead.append(c)
                    # Remove dead clients
                    if dead:
                        for c in dead:
                            try:
                                if c.get("sock"):
                                    c["sock"].close()
                            except Exception:
                                pass
                            try:
                                self._tcp_clients.remove(c)
                            except Exception:
                                pass

                # Append to stream buffer (split into lines and ignore empties)
                for line in full_nmea_packet.splitlines():
                    if line:
                        with self._lock:
                            self._stream.append(line)

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
                if self._tcp_server_sock:
                    try:
                        self._tcp_server_sock.close()
                    except Exception:
                        pass
                    self._tcp_server_sock = None
                # Close all client sockets
                for c in list(self._tcp_clients):
                    try:
                        if c.get("sock"):
                            c["sock"].close()
                    except Exception:
                        pass
                self._tcp_clients.clear()
            finally:
                self._sock = None
                print("Simulator socket closed.")

    def get_stream(self, limit: int = 100) -> List[str]:
        with self._lock:
            if limit <= 0:
                return []
            return list(self._stream)[-limit:]

    # --- AIS internal methods ---
    def _init_ais_targets(self) -> None:
        self.ais_targets = []
        for i in range(self.ais_num_targets):
            # Random small offset around own ship position (in nm), uniform in area up to ais_distribution_radius_nm
            r = math.sqrt(random.random()) * self.ais_distribution_radius_nm
            theta = random.uniform(0, 2 * math.pi)
            dx_nm = r * math.cos(theta)  # east-west in nautical miles
            dy_nm = r * math.sin(theta)  # north-south in nautical miles

            mmsi = 999000001 + i
            # Default seeding values; will be updated each tick
            sog = max(0.0, self.sog + random.uniform(-self.ais_max_sog_offset, self.ais_max_sog_offset))
            cog = (self.cog + random.uniform(-self.ais_max_cog_offset, self.ais_max_cog_offset)) % 360

            t = {
                "mmsi": mmsi,
                "lat": self.lat,
                "lon": self.lon,
                "sog": sog,
                "cog": cog,
                "hdg": cog,
                "name": self._make_vessel_name(i),
                # GPX-follow parameters
                "dx_nm": dx_nm,
                "dy_nm": dy_nm,
            }
            # Assign an offset along GPX if available
            if self._gpx_track:
                if self._gpx_start_time and self._gpx_end_time and all(p.get("time") is not None for p in self._gpx_track):
                    # Time-based offset within +/- 60s scaled by duration
                    total_s = max(1, int((self._gpx_end_time - self._gpx_start_time).total_seconds()))
                    # choose offset in a range proportional to duration but limited
                    max_off = min(300, max(30, total_s // 20))
                    t["gpx_time_offset_s"] = random.randint(-max_off, max_off)
                else:
                    # Index offset within +/- 50 points (bounded by track length)
                    t["gpx_index_offset"] = random.randint(-50, 50)
            self.ais_targets.append(t)

    def _update_ais_targets(self, dt_hours: float) -> None:
        if self._gpx_track:
            # AIS follow the GPX track with slight lateral and time/index offsets
            for t in self.ais_targets:
                base_lat = self.lat
                base_lon = self.lon
                base_sog = self.sog
                base_cog = self.cog
                if self._gpx_start_time and self._gpx_end_time and all(p.get("time") is not None for p in self._gpx_track):
                    # Time-based track
                    now_dt = (self.sim_time or datetime.utcnow().replace(tzinfo=timezone.utc))
                    off = int(t.get("gpx_time_offset_s", 0))
                    lat, lon, sog, cog = self._gpx_position_at_time(now_dt + timedelta(seconds=off))
                    base_lat, base_lon, base_sog, base_cog = lat, lon, sog, cog
                else:
                    # Index-based track (no timestamps)
                    cur = getattr(self, "_gpx_cursor", 0)
                    idx = cur + int(t.get("gpx_index_offset", 0))
                    lat, lon, sog, cog = self._gpx_position_at_index(idx)
                    base_lat, base_lon, base_sog, base_cog = lat, lon, sog, cog
                # Apply small static nm offsets in local N/E directions
                dy_nm = float(t.get("dy_nm", 0.0))
                dx_nm = float(t.get("dx_nm", 0.0))
                out_lat = base_lat + (dy_nm / 60.0)
                cos_lat = math.cos(math.radians(max(-89.99, min(89.99, base_lat)))) or 1e-6
                out_lon = base_lon + (dx_nm / (60.0 * cos_lat))
                t["lat"], t["lon"] = out_lat, out_lon
                # Slight variation around base sog/cog for realism
                t["sog"] = max(0.0, base_sog + random.uniform(-self.ais_max_sog_offset, self.ais_max_sog_offset))
                t["cog"] = (base_cog + random.uniform(-self.ais_max_cog_offset, self.ais_max_cog_offset)) % 360
                t["hdg"] = t["cog"]
        else:
            for t in self.ais_targets:
                # Nudge towards own ship speed/course with allowed offsets
                desired_cog = (self.cog + random.uniform(-self.ais_max_cog_offset, self.ais_max_cog_offset)) % 360
                # small smoothing
                t["cog"] = (0.8 * t["cog"] + 0.2 * desired_cog) % 360
                desired_sog = max(0.0, self.sog + random.uniform(-self.ais_max_sog_offset, self.ais_max_sog_offset))
                t["sog"] = max(0.0, 0.8 * t["sog"] + 0.2 * desired_sog)
                t["hdg"] = t["cog"]

                dist_nm = t["sog"] * dt_hours
                rad_cog = math.radians(t["cog"])
                t["lat"] += (dist_nm / 60.0) * math.cos(rad_cog)
                lat_for_lon = max(-89.99, min(89.99, t["lat"]))
                t["lon"] += (dist_nm / (60.0 * math.cos(math.radians(lat_for_lon)))) * math.sin(rad_cog)
                if t["lon"] > 180:
                    t["lon"] -= 360
                if t["lon"] < -180:
                    t["lon"] += 360

    def _build_ais_sentences(self, current_utc_time: datetime) -> str:
        if not self.ais_targets:
            return ""
        ts = current_utc_time.second
        msgs = []
        # Periodically send static data (Type 24 Part A) once per minute
        try:
            minute_key = int(current_utc_time.timestamp() // 60)
        except Exception:
            minute_key = None
        if minute_key is not None and minute_key != self._last_ais24_minute:
            self._last_ais24_minute = minute_key
            for t in self.ais_targets:
                base_name = t.get("name") or "Vessel"
                sog_v = float(t.get("sog", 0.0))
                cog_v = float(t.get("cog", 0.0))
                sog_str = f"{sog_v:.1f}"  # one decimal place
                cog_str = f"{int(round(cog_v)) % 360:03d}"  # 3 digits with leading zeros
                # AIS 6-bit doesn't support '|', so use '/' as separator
                suffix = f" {sog_str}/{cog_str}"
                maxlen = 20
                allowed = maxlen - len(suffix)
                if allowed < 1:
                    name24 = (f"{sog_str}/{cog_str}")[:maxlen]
                else:
                    name24 = base_name[:allowed] + suffix
                msgs.append(create_aivdm_type24_part_a(t["mmsi"], name24))
        for t in self.ais_targets:
            msgs.append(create_aivdm_type18(
                t["mmsi"], t["lat"], t["lon"], t["sog"], t["cog"], t["hdg"], ts
            ))
        return "".join(msgs)

    def _load_skippers(self):
        """Load skipper names from static/skippers.txt if available.
        Returns a list of non-empty lines; falls back to built-in names on error.
        """
        try:
            base = os.path.dirname(__file__)
            path = os.path.join(base, 'static', 'skippers.txt')
            names = []
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    name = line.strip()
                    if name:
                        names.append(name)
            return names
        except Exception:
            return []

    def _make_vessel_name(self, idx: int) -> str:
        # Prefer names from skippers.txt if available
        if isinstance(self._skipper_names, list) and self._skipper_names:
            try:
                return random.choice(self._skipper_names)
            except Exception:
                pass
        # Fallback: built-in generator
        first_names = [
            "Alex", "Sam", "Jamie", "Chris", "Taylor", "Jordan", "Casey", "Riley",
            "Avery", "Morgan", "Charlie", "Rowan", "Quinn", "Dakota", "Skyler"
        ]
        last_names = [
            "Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis",
            "Garcia", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
            "Wilson", "Anderson"
        ]
        fn = first_names[(idx * 7 + 3) % len(first_names)]
        ln = last_names[(idx * 11 + 5) % len(last_names)]
        return f"{fn} {ln}"

    def _tcp_clients_summary(self) -> List[Dict[str, str]]:
        out = []
        for c in self._tcp_clients:
            out.append({
                "address": f"{c.get('addr')}:{c.get('port')}",
                "connected_at": c.get("connected_at", "")
            })
        return out

    # --- GPX position helpers for AIS ---
    def _gpx_position_at_time(self, t: datetime):
        # Returns (lat, lon, sog, cog) at time t, clamped to track
        if not (self._gpx_track and self._gpx_start_time and self._gpx_end_time):
            return (self.lat, self.lon, self.sog, self.cog)
        if t <= self._gpx_start_time:
            p0, p1 = self._gpx_track[0], self._gpx_track[1]
        elif t >= self._gpx_end_time:
            p0, p1 = self._gpx_track[-2], self._gpx_track[-1]
        else:
            p0, p1 = None, None
            for i in range(1, len(self._gpx_track)):
                if self._gpx_track[i]["time"] >= t:
                    p0, p1 = self._gpx_track[i-1], self._gpx_track[i]
                    break
            if p0 is None or p1 is None:
                p0, p1 = self._gpx_track[-2], self._gpx_track[-1]
        t0, t1 = p0["time"], p1["time"]
        span = max(1e-6, (t1 - t0).total_seconds()) if (t0 and t1) else 1.0
        frac = min(1.0, max(0.0, (t - t0).total_seconds() / span)) if (t0 and t1) else 0.0
        lat = p0["lat"] + (p1["lat"] - p0["lat"]) * frac
        lon = p0["lon"] + (p1["lon"] - p0["lon"]) * frac
        seg_nm = self._haversine_nm(p0["lat"], p0["lon"], p1["lat"], p1["lon"])  # nm
        sog = max(0.0, (seg_nm / (span / 3600.0)))
        cog = self._bearing_deg(p0["lat"], p0["lon"], p1["lat"], p1["lon"]) % 360
        return (lat, lon, sog, cog)

    def _gpx_position_at_index(self, idx: int):
        # Returns (lat, lon, sog, cog) at index idx (clamped), using next point for cog/sog
        if not self._gpx_track:
            return (self.lat, self.lon, self.sog, self.cog)
        n = len(self._gpx_track)
        if n < 2:
            return (self.lat, self.lon, self.sog, self.cog)
        i0 = max(0, min(n - 2, int(idx)))
        i1 = i0 + 1
        p0, p1 = self._gpx_track[i0], self._gpx_track[i1]
        lat, lon = p0["lat"], p0["lon"]
        seg_nm = self._haversine_nm(p0["lat"], p0["lon"], p1["lat"], p1["lon"])  # nm
        # Approximate speed by segment length over interval seconds
        sog = max(0.0, seg_nm / max(1e-6, (self.interval / 3600.0)))
        cog = self._bearing_deg(p0["lat"], p0["lon"], p1["lat"], p1["lon"]) % 360
        return (lat, lon, sog, cog)

    # --- GPX helpers ---
    def _prepare_gpx(self, track):
        if not track:
            return None
        out = []
        for p in track:
            try:
                lat = float(p.get("lat"))
                lon = float(p.get("lon"))
            except Exception:
                continue
            t = p.get("time")
            if isinstance(t, datetime):
                if t.tzinfo is None:
                    t = t.replace(tzinfo=timezone.utc)
                t = t.astimezone(timezone.utc)
            else:
                t = None
            out.append({"lat": lat, "lon": lon, "time": t})
        if len(out) < 2:
            return None
        # Ensure monotonic by time if present
        if all(o.get("time") is not None for o in out):
            out.sort(key=lambda x: x["time"])  # type: ignore
        return out

    @staticmethod
    def _haversine_nm(lat1, lon1, lat2, lon2):
        R_km = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        km = R_km * c
        return km * 0.539957

    @staticmethod
    def _bearing_deg(lat1, lon1, lat2, lon2):
        y = math.sin(math.radians(lon2 - lon1)) * math.cos(math.radians(lat2))
        x = math.cos(math.radians(lat1)) * math.sin(math.radians(lat2)) - math.sin(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.cos(math.radians(lon2 - lon1))
        brng = (math.degrees(math.atan2(y, x)) + 360) % 360
        return brng

    def _update_from_gpx(self, current_utc_time: datetime) -> None:
        # If track has timestamps: interpolate by time; else step through points uniformly by distance
        if not self._gpx_track:
            return
        # Determine target time
        if self.sim_time is None:
            tnow = current_utc_time
        else:
            tnow = self.sim_time

        # If we have times for all points, use them
        if self._gpx_start_time and self._gpx_end_time and all(p.get("time") is not None for p in self._gpx_track):
            if tnow <= self._gpx_start_time:
                p = self._gpx_track[0]
                self.lat, self.lon = p["lat"], p["lon"]
                self.sog = 0.0
                # keep previous cog
                return
            if tnow >= self._gpx_end_time:
                p = self._gpx_track[-1]
                self.lat, self.lon = p["lat"], p["lon"]
                self.sog = 0.0
                return
            # Find surrounding points
            # Linear scan is OK for moderate sizes; could be optimized
            prev = None
            nxt = None
            for i in range(1, len(self._gpx_track)):
                if self._gpx_track[i]["time"] >= tnow:
                    prev = self._gpx_track[i-1]
                    nxt = self._gpx_track[i]
                    break
            if not prev or not nxt:
                return
            t0 = prev["time"]
            t1 = nxt["time"]
            span = max(1e-6, (t1 - t0).total_seconds())
            frac = min(1.0, max(0.0, (tnow - t0).total_seconds() / span))
            self.lat = prev["lat"] + (nxt["lat"] - prev["lat"]) * frac
            self.lon = prev["lon"] + (nxt["lon"] - prev["lon"]) * frac
            seg_nm = self._haversine_nm(prev["lat"], prev["lon"], nxt["lat"], nxt["lon"])  # full segment dist
            # Use segment average speed (constant across segment) for more natural AIS behavior
            self.sog = max(0.0, (seg_nm / (span / 3600.0)))
            self.cog = self._bearing_deg(prev["lat"], prev["lon"], nxt["lat"], nxt["lon"]) % 360
        else:
            # No timestamps: advance along the polyline at current SOG
            # We'll approximate by moving towards the next point by distance each tick
            if not hasattr(self, "_gpx_cursor"):
                self._gpx_cursor = 0
                self.lat = self._gpx_track[0]["lat"]
                self.lon = self._gpx_track[0]["lon"]
            target = self._gpx_track[min(self._gpx_cursor+1, len(self._gpx_track)-1)]
            dist_to_target = self._haversine_nm(self.lat, self.lon, target["lat"], target["lon"])  # nm
            step_nm = max(0.0, self.sog) * (self.interval / 3600.0)
            if dist_to_target <= 1e-3 or step_nm >= dist_to_target:
                # Move to next point
                self.lat, self.lon = target["lat"], target["lon"]
                self._gpx_cursor = min(self._gpx_cursor+1, len(self._gpx_track)-2)
                nxt = self._gpx_track[self._gpx_cursor+1]
                self.cog = self._bearing_deg(target["lat"], target["lon"], nxt["lat"], nxt["lon"]) % 360
            else:
                # Interpolate small step along bearing
                br = math.radians(self._bearing_deg(self.lat, self.lon, target["lat"], target["lon"]))
                # Approximate small distance move in degrees
                dlat = (step_nm / 60.0) * math.cos(br)
                dlon = (step_nm / (60.0 * max(1e-6, math.cos(math.radians(self.lat))))) * math.sin(br)
                self.lat += dlat
                self.lon += dlon
                self.cog = (math.degrees(br) + 360) % 360


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
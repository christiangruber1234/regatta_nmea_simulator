from flask import Flask, render_template, request, jsonify
import os
import uuid
from io import BytesIO
from xml.etree import ElementTree as ET
from datetime import datetime, timezone, timedelta
from datetime import datetime, timezone
from threading import Lock
from typing import Optional
from nmea_simulator import NMEASimulator

app = Flask(__name__)

# Global simulator instance and lock
sim_lock = Lock()
simulator: Optional[NMEASimulator] = None

# In-memory GPX store: id -> {"points": List[{lat, lon, time_dt or None}], "meta": {...}}
GPX_STORE = {}


def get_simulator() -> Optional[NMEASimulator]:
    global simulator
    return simulator


def set_simulator(sim: Optional[NMEASimulator]) -> None:
    global simulator
    simulator = sim


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/data")
def data_page():
    return render_template("data.html")


@app.route("/ais")
def ais_page():
    return render_template("ais.html")


@app.route("/api/status", methods=["GET"]) 
def api_status():
    sim = get_simulator()
    if sim is None:
        return jsonify({"running": False})
    st = sim.status()
    # Annotate whether GPX mode is active
    st["gpx_active"] = bool(st.get("gpx_track_info"))
    return jsonify(st)


@app.route("/api/stream", methods=["GET"]) 
def api_stream():
    sim = get_simulator()
    if sim is None:
        return jsonify({"lines": []})
    try:
        limit = int(request.args.get("limit", 100))
    except Exception:
        limit = 100
    lines = sim.get_stream(limit=limit)
    return jsonify({"lines": lines})


@app.route("/api/start", methods=["POST"]) 
def api_start():
    data = request.get_json(force=True) or {}

    try:
        start_dt_str = data.get("start_datetime")
        start_dt = None
        if start_dt_str:
            # Accept ISO with 'Z' suffix
            def _parse_time_iso_local(ts: str):
                try:
                    s = ts.strip()
                    if s.endswith("Z"):
                        s = s[:-1] + "+00:00"
                    dt = datetime.fromisoformat(s)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt.astimezone(timezone.utc)
                except Exception:
                    return None
            start_dt = _parse_time_iso_local(start_dt_str)

        # Validate/normalize UDP destination host: 0.0.0.0 is not a valid destination
        raw_host = str(data.get("host", "127.0.0.1")).strip()
        if raw_host in ("0.0.0.0", "", "any", "all"):
            raw_host = "127.0.0.1"

        # GPX handling if provided
        gpx_id = data.get("gpx_id")
        gpx_points = None
        gpx_meta = None
        if gpx_id:
            g = GPX_STORE.get(str(gpx_id))
            if not g:
                return jsonify({"ok": False, "error": "Invalid gpx_id"}), 400
            gpx_points = g.get("points")
            gpx_meta = g.get("meta")
        # Optional GPX cursor controls from UI
        gpx_offset_s = data.get("gpx_offset_s")
        gpx_start_fraction = data.get("gpx_start_fraction")

        params = dict(
            host=raw_host,
            port=int(data.get("port", 10110)),
            tcp_port=int(data.get("tcp_port", 10111)),
            tcp_host=str(data.get("tcp_host", "0.0.0.0")).strip() or "0.0.0.0",
            interval=float(data.get("interval", 1.0)),
            wind_enabled=bool(data.get("wind_enabled", True)),
            start_lat=float(data.get("lat", 47.0707)),
            start_lon=float(data.get("lon", 15.4395)),
            sog_knots=float(data.get("sog", 5.0)),
            cog_degrees=float(data.get("cog", 45.0)),
            tws_knots=float(data.get("tws", 10.0)),
            twd_degrees=float(data.get("twd", 270.0)),
            mag_variation=float(data.get("magvar", -2.5)),
            start_datetime=start_dt,
            ais_num_targets=int(data.get("ais_num_targets", 20)),
            ais_max_cog_offset=float(data.get("ais_max_cog_offset", 20.0)),
            ais_max_sog_offset=float(data.get("ais_max_sog_offset", 2.0)),
            ais_distribution_radius_nm=float(data.get("ais_distribution_radius_nm", 10.0)),
            gpx_track=gpx_points,
        )
        # If GPX provided and it has timestamps, align simulator start to requested offset or GPX start
        if gpx_meta and gpx_meta.get("start_time"):
            try:
                gpx_start_dt = datetime.fromisoformat(gpx_meta["start_time"]).astimezone(timezone.utc)
            except Exception:
                gpx_start_dt = None
            if gpx_start_dt is not None:
                if gpx_offset_s is not None:
                    try:
                        off = int(float(gpx_offset_s))
                        params["start_datetime"] = (gpx_start_dt + timedelta(seconds=off)).astimezone(timezone.utc)
                    except Exception:
                        pass
                elif start_dt is None:
                    params["start_datetime"] = gpx_start_dt
        # If GPX provided, set initial lat/lon (and sog/cog when possible) to the selected slider position
        if gpx_points:
            try:
                if gpx_meta and gpx_meta.get("has_time"):
                    # Determine target time: explicit start_datetime beats offset; else offset from GPX start
                    target_dt = params.get("start_datetime") or (gpx_start_dt if 'gpx_start_dt' in locals() else None)
                    # Fallback: GPX start
                    if target_dt is None:
                        target_dt = datetime.fromisoformat(gpx_meta["start_time"]).astimezone(timezone.utc) if gpx_meta.get("start_time") else None
                    # Find surrounding points and interpolate
                    prev = None
                    nxt = None
                    if target_dt is not None:
                        for i in range(1, len(gpx_points)):
                            t1 = gpx_points[i].get("time")
                            if t1 and t1 >= target_dt:
                                prev = gpx_points[i-1]
                                nxt = gpx_points[i]
                                break
                    if not prev or not nxt:
                        prev = gpx_points[0]
                        nxt = gpx_points[1]
                    t0 = prev.get("time")
                    t1 = nxt.get("time")
                    if t0 and t1 and target_dt:
                        span = max(1e-6, (t1 - t0).total_seconds())
                        frac = min(1.0, max(0.0, (target_dt - t0).total_seconds() / span))
                        lat = float(prev["lat"]) + (float(nxt["lat"]) - float(prev["lat"])) * frac
                        lon = float(prev["lon"]) + (float(nxt["lon"]) - float(prev["lon"])) * frac
                        params["start_lat"], params["start_lon"] = lat, lon
                        # Set initial sog/cog to segment values for consistent AIS init
                        try:
                            # Distance in nm and duration to hours
                            from math import atan2, degrees, radians, sin, cos, asin, sqrt
                            # Haversine
                            R_km = 6371.0
                            dlat = radians(nxt["lat"] - prev["lat"])  # type: ignore
                            dlon = radians(nxt["lon"] - prev["lon"])  # type: ignore
                            a = sin(dlat/2)**2 + cos(radians(prev["lat"])) * cos(radians(nxt["lat"])) * sin(dlon/2)**2  # type: ignore
                            c = 2 * asin(sqrt(a))
                            km = R_km * c
                            nm = km * 0.539957
                            hours = span / 3600.0
                            sog0 = nm / hours if hours > 0 else 0.0
                            # Bearing
                            y = sin(radians(nxt["lon"] - prev["lon"])) * cos(radians(nxt["lat"]))  # type: ignore
                            x = cos(radians(prev["lat"])) * sin(radians(nxt["lat"])) - sin(radians(prev["lat"])) * cos(radians(nxt["lat"])) * cos(radians(nxt["lon"] - prev["lon"]))  # type: ignore
                            brg = (degrees(atan2(y, x)) + 360.0) % 360.0
                            params["sog_knots"] = float(sog0)
                            params["cog_degrees"] = float(brg)
                        except Exception:
                            pass
                    else:
                        # Fallback to first point
                        params["start_lat"] = float(gpx_points[0]["lat"])  # type: ignore
                        params["start_lon"] = float(gpx_points[0]["lon"])  # type: ignore
                else:
                    # No times: use fraction if provided, else first point
                    if gpx_start_fraction is not None:
                        try:
                            f = max(0.0, min(1.0, float(gpx_start_fraction)))
                            idx = int(round(f * (len(gpx_points) - 1)))
                            idx = max(0, min(idx, len(gpx_points) - 1))
                            params["start_lat"] = float(gpx_points[idx]["lat"])  # type: ignore
                            params["start_lon"] = float(gpx_points[idx]["lon"])  # type: ignore
                        except Exception:
                            params["start_lat"] = float(gpx_points[0]["lat"])  # type: ignore
                            params["start_lon"] = float(gpx_points[0]["lon"])  # type: ignore
                    else:
                        params["start_lat"] = float(gpx_points[0]["lat"])  # type: ignore
                        params["start_lon"] = float(gpx_points[0]["lon"])  # type: ignore
            except Exception:
                pass
        # If GPX has no timestamps and a start fraction is provided, forward to simulator
        if gpx_points and (gpx_meta and not gpx_meta.get("has_time")) and gpx_start_fraction is not None:
            try:
                params["gpx_start_fraction"] = max(0.0, min(1.0, float(gpx_start_fraction)))
            except Exception:
                pass
    except Exception as e:
        return jsonify({"ok": False, "error": f"Invalid parameter: {e}"}), 400

    with sim_lock:
        sim = get_simulator()
        if sim and sim.is_running():
            return jsonify({"ok": False, "error": "Simulator already running"}), 409
        try:
            sim = NMEASimulator(**params)
            sim.start()
            set_simulator(sim)
        except Exception as e:
            # Ensure any partially created simulator is stopped/cleared
            try:
                if sim:
                    sim.stop()
            except Exception:
                pass
            set_simulator(None)
            return jsonify({"ok": False, "error": f"Failed to start simulator: {e}"}), 500
    return jsonify({"ok": True, "status": sim.status()})


def _parse_time_iso(ts: str) -> Optional[datetime]:
    try:
        s = ts.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _haversine_nm(lat1, lon1, lat2, lon2):
    from math import radians, sin, cos, asin, sqrt
    R_km = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    km = R_km * c
    return km * 0.539957  # km to nautical miles


@app.route("/api/upload_gpx", methods=["POST"])
def api_upload_gpx():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No file"}), 400
    f = request.files["file"]
    content = f.read()
    if not content:
        return jsonify({"ok": False, "error": "Empty file"}), 400
    try:
        root = ET.fromstring(content)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Invalid GPX: {e}"}), 400

    # GPX namespaces are common; ignore by stripping
    def _strip_ns(tag):
        return tag.split("}")[-1]

    pts = []
    for trk in root.iter():
        if _strip_ns(trk.tag) == "trkseg":
            for tp in trk:
                if _strip_ns(tp.tag) != "trkpt":
                    continue
                try:
                    lat = float(tp.attrib.get("lat"))
                    lon = float(tp.attrib.get("lon"))
                except Exception:
                    continue
                t_el = None
                for ch in tp:
                    if _strip_ns(ch.tag) == "time":
                        t_el = ch
                        break
                t_dt = _parse_time_iso(t_el.text) if (t_el is not None and t_el.text) else None
                pts.append({"lat": lat, "lon": lon, "time": t_dt})

    if len(pts) < 2:
        return jsonify({"ok": False, "error": "GPX has fewer than 2 track points"}), 400

    # Compute meta
    length_nm = 0.0
    minlat = min(p["lat"] for p in pts)
    maxlat = max(p["lat"] for p in pts)
    minlon = min(p["lon"] for p in pts)
    maxlon = max(p["lon"] for p in pts)
    has_time = all(p.get("time") is not None for p in pts)
    start_time = next((p["time"] for p in pts if p.get("time") is not None), None)
    end_time = None
    for i in range(1, len(pts)):
        p0, p1 = pts[i-1], pts[i]
        length_nm += _haversine_nm(p0["lat"], p0["lon"], p1["lat"], p1["lon"])
        if p1.get("time") is not None:
            end_time = p1["time"]
    duration_s = None
    if start_time and end_time:
        duration_s = int((end_time - start_time).total_seconds())

    # Downsample path for map preview (max ~500 points)
    step = max(1, len(pts) // 500)
    path = [[p["lat"], p["lon"]] for i, p in enumerate(pts) if i % step == 0]
    if path[-1] != [pts[-1]["lat"], pts[-1]["lon"]]:
        path.append([pts[-1]["lat"], pts[-1]["lon"]])

    # Build a time-based preview timeline for accurate slider preview (max ~600 samples)
    timeline = None
    if has_time and start_time and end_time and isinstance(duration_s, int) and duration_s > 0:
        try:
            # Helper: interpolate at a given datetime
            def interp_at(tdt):
                prev = None
                nxtp = None
                for i in range(1, len(pts)):
                    ti = pts[i].get("time")
                    if ti and ti >= tdt:
                        prev = pts[i-1]
                        nxtp = pts[i]
                        break
                if prev is None or nxtp is None:
                    prev = pts[-2]
                    nxtp = pts[-1]
                t0, t1 = prev.get("time"), nxtp.get("time")
                if t0 and t1:
                    span = max(1e-6, (t1 - t0).total_seconds())
                    frac = min(1.0, max(0.0, (tdt - t0).total_seconds() / span))
                    lat = float(prev["lat"]) + (float(nxtp["lat"]) - float(prev["lat"])) * frac
                    lon = float(prev["lon"]) + (float(nxtp["lon"]) - float(prev["lon"])) * frac
                else:
                    lat, lon = float(prev["lat"]), float(prev["lon"])
                return (lat, lon)

            max_samples = 600
            step_s = max(1, duration_s // max_samples)
            timeline = []
            tcur = start_time
            rel = 0
            while rel <= duration_s:
                lat, lon = interp_at(tcur)
                timeline.append([int(rel), lat, lon])
                rel += step_s
                tcur = tcur + timedelta(seconds=step_s)
            # Ensure last point included exactly
            if timeline and timeline[-1][0] < duration_s:
                lat, lon = interp_at(end_time)
                timeline.append([int(duration_s), lat, lon])
        except Exception:
            timeline = None

    gpx_id = str(uuid.uuid4())
    # Serialize times to ISO for storage meta; keep datetime objects in points for the simulator
    meta = {
        "id": gpx_id,
        "points_count": len(pts),
        "length_nm": round(length_nm, 3),
        "has_time": bool(has_time),
        "start_time": start_time.astimezone(timezone.utc).isoformat() if start_time else None,
        "end_time": end_time.astimezone(timezone.utc).isoformat() if end_time else None,
        "duration_s": duration_s,
        "bbox": {"minlat": minlat, "maxlat": maxlat, "minlon": minlon, "maxlon": maxlon},
        "path": path,
        "timeline": timeline,
    }
    GPX_STORE[gpx_id] = {"points": pts, "meta": meta}
    return jsonify({"ok": True, "gpx": meta})


@app.route("/api/stop", methods=["POST"]) 
def api_stop():
    with sim_lock:
        sim = get_simulator()
        if sim is None or not sim.is_running():
            return jsonify({"ok": False, "error": "Simulator not running"}), 409
        sim.stop()
        set_simulator(sim)
    return jsonify({"ok": True, "status": sim.status()})


@app.route("/api/restart", methods=["POST"]) 
def api_restart():
    data = request.get_json(force=True) or {}
    # Stop first
    with sim_lock:
        sim = get_simulator()
        if sim and sim.is_running():
            sim.stop()
    # Start with new parameters
    return api_start()


if __name__ == "__main__":
    # For development use only; allow overriding port via env for local conflicts
    port = int(os.environ.get("PORT", 5080))
    app.run(host="0.0.0.0", port=port, debug=True)

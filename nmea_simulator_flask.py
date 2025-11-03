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
            start_dt = datetime.fromisoformat(start_dt_str)
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            else:
                start_dt = start_dt.astimezone(timezone.utc)

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
        # If GPX provided and it has timestamps, align simulator start to GPX start unless user explicitly provided start_datetime
        if gpx_meta and gpx_meta.get("start_time") and start_dt is None:
            try:
                params["start_datetime"] = datetime.fromisoformat(gpx_meta["start_time"]).astimezone(timezone.utc)
            except Exception:
                pass
        # If GPX provided, override initial lat/lon to the first track point
        if gpx_points:
            try:
                params["start_lat"] = float(gpx_points[0]["lat"])  # type: ignore
                params["start_lon"] = float(gpx_points[0]["lon"])  # type: ignore
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

    # Downsample path for preview (max ~500 points)
    step = max(1, len(pts) // 500)
    path = [[p["lat"], p["lon"]] for i, p in enumerate(pts) if i % step == 0]
    if path[-1] != [pts[-1]["lat"], pts[-1]["lon"]]:
        path.append([pts[-1]["lat"], pts[-1]["lon"]])

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

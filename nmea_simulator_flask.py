from flask import Flask, render_template, request, jsonify
from datetime import datetime, timezone
from threading import Lock
from typing import Optional
from nmea_simulator import NMEASimulator

app = Flask(__name__)

# Global simulator instance and lock
sim_lock = Lock()
simulator: Optional[NMEASimulator] = None


def get_simulator() -> Optional[NMEASimulator]:
    global simulator
    return simulator


def set_simulator(sim: NMEASimulator | None) -> None:
    global simulator
    simulator = sim


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status", methods=["GET"]) 
def api_status():
    sim = get_simulator()
    if sim is None:
        return jsonify({"running": False})
    return jsonify(sim.status())


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

        params = dict(
            host=data.get("host", "127.0.0.1"),
            port=int(data.get("port", 10110)),
            interval=float(data.get("interval", 1.0)),
            wind_enabled=bool(data.get("wind_enabled", False)),
            start_lat=float(data.get("lat", 47.0707)),
            start_lon=float(data.get("lon", 15.4395)),
            sog_knots=float(data.get("sog", 5.0)),
            cog_degrees=float(data.get("cog", 45.0)),
            tws_knots=float(data.get("tws", 10.0)),
            twd_degrees=float(data.get("twd", 270.0)),
            mag_variation=float(data.get("magvar", -2.5)),
            start_datetime=start_dt,
        )
    except Exception as e:
        return jsonify({"ok": False, "error": f"Invalid parameter: {e}"}), 400

    with sim_lock:
        sim = get_simulator()
        if sim and sim.is_running():
            return jsonify({"ok": False, "error": "Simulator already running"}), 409
        sim = NMEASimulator(**params)
        sim.start()
        set_simulator(sim)
    return jsonify({"ok": True, "status": sim.status()})


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
    # For development use only
    app.run(host="0.0.0.0", port=5000, debug=True)

# Regatta NMEA 0183 Simulator

A lightweight, batteries-included NMEA 0183 simulator with a web UI, UDP output, optional TCP streaming, AIS target simulation, GPX playback, and live maps with seamarks.

Fork note: This project was originally created by Christian Heiling and forked from his work.

## Features

- NMEA output over UDP and TCP
  - GPS/GNSS: GPRMC, GPGGA, GPVTG, GPGSA, GPGSV
  - Wind (optional): WIMWD, WIMWV (True and Apparent)
  - AIS: !AIVDM Type 18 (Class B position) and Type 24 Part A (static data)
  - Heading (optional): HCHDT (true heading derived from COG when enabled)
- Realistic simulation: SOG, COG, wind speed/direction and position evolve over time
- AIS targets: configurable count, random spatial distribution, speed/course offsets
- Built-in TCP server to stream the same NMEA payload to multiple clients
- GPX track mode
  - Upload a GPX and play the simulation along the track by time or by index
  - Precise slider preview (time-aligned) and simulator start alignment at the selected position
  - AIS targets follow the GPX with slight offsets for realism
  - Server-side saving of uploaded GPX under `uploads/gpx/`
- Unified header controls on all pages
  - Start / Stop / Restart in the header, centered
  - Live “RUNNING HH:MM:SS” timer and a pulsing green outline while running
- Web UI (Leaflet + OSM + OpenSeaMap)
  - SETTINGS page: network, initial parameters, manual vs GPX mode, wind
  - AIS page: configure AIS targets and visualize them
  - STATUS page: rich GNSS view, TCP clients, and a live NMEA/AIS console
  - Theme toggle (light/dark) switches map tiles; OpenSeaMap seamarks overlay

## Requirements

- Python 3.8+
- Flask (declared in `requirements.txt`)

## Install and run (Web UI)

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run the Flask app; default port is 5080. Use PORT to override.
PORT=5080 .venv/bin/python nmea_simulator_flask.py
```

Then open http://localhost:5080 in your browser.

Tip: If port 5080 is already in use on your machine, set a different `PORT`, e.g. `PORT=5090`.

## Install and run (CLI)

You can run the simulator without the web UI. It will send NMEA over UDP only.

```bash
python3 nmea_simulator.py --help
python3 nmea_simulator.py \
  --host 127.0.0.1 \
  --port 10110 \
  --interval 1.0 \
  --wind \
  --lat 42.7157693493 \
  --lon 16.2321737476 \
  --sog 5 --cog 185 --tws 10 --twd 270 --magvar -2.5 \
  --start-datetime 2025-01-01T12:00:00Z
```

Defaults: UDP to 127.0.0.1:10110, 1 Hz.

## Web UI overview

Pages (templates in `templates/`):

- SETTINGS (`/`)
  - Header controls: Start / Stop / Restart with running timer
  - Network
    - UDP address (default 127.0.0.1)
    - UDP Port (default 10110)
    - TCP interface (default 0.0.0.0)
    - TCP Port (default 10111)
  - Initial parameters
    - Manual vs GPX mode (toggle)
    - Manual: Start Latitude/Longitude, Start Date & Time (UTC), Interval (s), Initial SOG/COG, Magnetic Variation (°)
    - GPX: Upload file, Interval (s), filename bar, slider for time or index with precise preview
  - Wind
    - Toggle On/Off; shows/hides TWS/TWD inputs
  - Heading
    - Toggle to emit `$HCHDT` (true heading) computed from current COG
  - Map
    - Click/drag to set starting position (manual mode); theme-aware tiles; OpenSeaMap seamarks overlay

- AIS (`/ais`)
  - Header controls: Start / Stop / Restart with running timer
  - Options: Number of targets, max course/speed offsets, distribution radius (nm)
  - Apply & Restart to reconfigure
  - Map + table of simulated AIS targets; auto-fit to targets initially

- STATUS (`/data`)
  - Header controls: Start / Stop / Restart with running timer
  - Live status (position, SOG/COG, wind, sim time)
  - GNSS satellites (sky plot + SNR bars) and DOPs
  - TCP clients list
  - Live data stream console (last 200 lines)

Static assets are in `static/`:

- `static/js/regatta_nmea_simulator.js` — SETTINGS page logic (map, start/restart payloads, GPX UI)
- `static/js/header_controls.js` — Shared header Start/Stop/Restart with running timer across pages
- `static/css/styles.css` — Shared styles, theme, header layout, animated running state

Notes:
- The old inline status line under the Wind section was removed; the header controls reflect the state instead.

## REST API

All endpoints return/consume JSON.

- GET `/api/status`
  - Returns: `{ running, host, port, tcp_port, tcp_host, interval, wind_enabled, heading_enabled, lat, lon, sog, cog, tws, twd, magvar, sim_time, started_at, gnss, ais, stream_size, tcp_clients, gpx_track_info }`
  - `started_at` is an ISO8601 timestamp used for the running timer
  - `gpx_track_info` includes `{ points, start_time, end_time, duration_s, has_time, progress }`, where `progress` is `{ mode: 'time', offset_s }` or `{ mode: 'index', fraction }`

- GET `/api/stream?limit=100`
  - Returns the latest NMEA/AIS lines (up to `limit`, default 100)
  - Shape: `{ lines: ["$GPRMC,...", ...] }`

- POST `/api/start`
  - Starts the simulator. Body fields (all optional with defaults):
    - UDP: `host` (dest, defaults 127.0.0.1 if invalid), `port`
    - TCP: `tcp_host` (listen interface), `tcp_port` (set to null/0 to disable)
    - Timing: `interval` seconds; `start_datetime` ISO8601 (UTC assumed if no tz)
    - Position: `lat`, `lon`
    - Navigation: `sog`, `cog`, `magvar`
  - Wind: `wind_enabled` (bool), `tws`, `twd`
  - Heading: `heading_enabled` (bool) to add HDT sentence derived from COG
    - AIS: `ais_num_targets`, `ais_max_cog_offset`, `ais_max_sog_offset`, `ais_distribution_radius_nm`
    - GPX: `gpx_id` (from upload), and one of:
      - `gpx_offset_s` (start at GPX start time + offset seconds)
      - `gpx_start_fraction` (0..1) for tracks without timestamps

- POST `/api/stop`
  - Stops the simulator.

- POST `/api/restart`
  - Stops (if running) and starts with the provided body parameters (same as `/api/start`).

- POST `/api/upload_gpx`
  - Upload a GPX file to play back
  - Returns `{ ok, gpx }` where `gpx` includes:
    - `id`, `filename`, `saved_path` (server-side saved under `uploads/gpx/`)
    - `points_count`, `length_nm`, `has_time`, `start_time`, `end_time`, `duration_s`
    - `path` (downsampled coordinates for plotting), and `timeline` (time→position samples for accurate slider)

Notes:
- The UDP destination host is normalized: `0.0.0.0`/empty becomes `127.0.0.1`.
- TCP streaming binds to `tcp_host:tcp_port` and broadcasts the same NMEA payload sent over UDP.

## NMEASimulator class

Location: `nmea_simulator.py`

Constructor (key parameters):

```
NMEASimulator(
  host="127.0.0.1", port=10110,
  interval=1.0,
  wind_enabled=True,
  heading_enabled=False,
  start_lat=..., start_lon=...,
  sog_knots=5.0, cog_degrees=185.0,
  tws_knots=10.0, twd_degrees=270.0,
  mag_variation=-2.5,
  start_datetime: Optional[datetime]=None,
  ais_num_targets=0,
  ais_max_cog_offset=20.0,
  ais_max_sog_offset=2.0,
  ais_distribution_radius_nm=1.0,
  tcp_port=10111,
  tcp_host="0.0.0.0",
)
```

Methods:

- `start()` — starts background thread and begins emitting data
- `stop(timeout: float = 5.0)` — stops and joins the thread
- `restart(**kwargs)` — stop, set attributes, start
- `status() -> dict` — current state summary (includes GNSS/AIS and TCP clients)
- `get_stream(limit: int = 100) -> List[str]` — recent NMEA/AIS lines

Outputs each tick:

- GNSS/NMEA: GPRMC, GPGGA, GPVTG, GPGSA, GPGSV
- Wind (when enabled): WIMWD, WIMWV (True + Apparent)
- Heading (when enabled): HCHDT (True heading)
- AIS (when configured): !AIVDM Type 18, and periodic Type 24 Part A

## Map tiles and night mode

- Light: standard OpenStreetMap tiles
- Dark/Night: Carto “Dark Matter” tiles (OSM-derived) used when night theme is selected
- OpenSeaMap seamarks overlay enabled on all maps
- The UI hides the Leaflet attribution control for a cleaner look; ensure you review upstream tile provider terms if redistributing.

## Troubleshooting

- Flask server fails with: “Port 5080 is in use”
  - Run on a different port: `PORT=5090 .venv/bin/python nmea_simulator_flask.py`
- No NMEA received by your app
  - Confirm your consumer is listening on the same UDP port (default 10110)
  - If you set UDP destination `0.0.0.0`, it will be normalized to `127.0.0.1`
  - Firewalls may block UDP/TCP locally
- TCP clients don’t connect
  - Ensure TCP server is enabled (non-null `tcp_port`) and listening interface (`tcp_host`) is reachable from the client host

## Project layout

- `nmea_simulator.py` — NMEASimulator class and CLI
- `nmea_simulator_flask.py` — Flask server exposing the UI and REST API
- `templates/` — `index.html` (SETTINGS), `ais.html` (AIS), `data.html` (STATUS)
- `static/js/regatta_nmea_simulator.js` — SETTINGS page logic
- `static/js/header_controls.js` — Header Start/Stop/Restart on all pages
- `static/css/styles.css` — shared styles, theme, header and button animations
- `static/skippers.txt` — optional names used for AIS vessel names
- `requirements.txt` — Python dependencies (Flask)

## License

MIT License. See the repository for details.

# Regatta NMEA 0183 Simulator

A feature-rich NMEA 0183 simulator with a web UI, UDP/TCP output, AIS target simulation, GPX track playback, and live maps with seamarks. Perfect for testing marine navigation applications, chart plotters, and instrument displays.

**Author:** Christian Heiling  
**License:** MIT

## Features

- NMEA output over UDP and TCP
  - GPS/GNSS: GPRMC, GPGGA, GPVTG, GPGSA, GPGSV
  - Wind (optional): WIMWD, WIMWV (True and Apparent)
  - AIS: !AIVDM Type 18 (Class B position) and Type 24 Part A (static data)
  - Heading (optional): HCHDT (true heading derived from COG when enabled)
  - Sensors (optional): Depth (SDDBT, SDDPT), Water Temperature (WIMTW), Battery Voltage (IIXDR), Air Temperature (IIXDR), Tank Levels (IIXDR)
- Realistic simulation: SOG, COG, wind speed/direction, position, and sensor values evolve over time
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

## Web UI Overview

### Pages

**SIMULATOR** (`/` - `templates/index.html`)
- **Unified Header Controls:** Start/Stop/Reset buttons with live running timer (HH:MM:SS) and animated status indicator
- **Navigation Tabs:** Quick access to SIMULATOR, STATUS, and day/night theme toggle
- **Network Configuration:**
  - UDP destination address (default: 127.0.0.1)
  - UDP port (default: 10110)
  - TCP server interface (default: 0.0.0.0 for all interfaces)
  - TCP server port (default: 10111)
- **Starting Conditions - Toggle between Manual and GPX modes:**
  - **Manual Mode:**
    - Position: Starting latitude/longitude
    - Date & Time: Start datetime (UTC) and interval (seconds)
    - Speed & Course: Initial SOG (knots) and COG (degrees true)
    - Heading: Toggle to enable/disable HCHDT sentence; magnetic variation setting
  - **GPX Mode:**
    - File upload with drag-and-drop support
    - Display uploaded filename and track metadata (points, length, duration)
    - Interactive slider for preview:
      - Time-based (for tracks with timestamps) showing position at specific time
      - Index-based (for tracks without timestamps) showing position by percentage
    - Interval setting applies to both modes
- **Wind Configuration:**
  - Toggle On/Off
  - True Wind Speed (TWS) in knots
  - True Wind Direction (TWD) in degrees true
- **Sensor Configuration** (each with toggle and parameters):
  - **Depth:** Depth in meters and transducer offset
  - **Water Temperature:** Temperature in °C
  - **Battery Voltage:** Voltage in volts
  - **Air Temperature:** Temperature in °C
  - **Tank Levels:** Percentage for FreshWater, Fuel, and WasteWater tanks
- **AIS Configuration:**
  - Number of targets
  - Maximum COG offset (degrees)
  - Maximum SOG offset (knots)
  - Distribution radius (nautical miles)
- **Interactive Map:**
  - Click to set starting position in manual mode
  - Displays GPX track path when uploaded
  - Theme-aware tiles (OSM standard or Carto Dark Matter)
  - OpenSeaMap overlay for nautical features

**AIS** (`/ais` - `templates/ais.html`)
- **Header Controls:** Same unified controls as main page
- **Configuration Panel:**
  - Number of AIS targets
  - Maximum course/speed offsets for realistic fleet simulation
  - Spatial distribution radius around main vessel
  - Apply & Restart button to reconfigure targets
- **Visualization:**
  - Interactive map with all AIS targets displayed
  - Auto-fit to show all targets on initial load
  - Table view showing MMSI, vessel name, position, SOG, COG for each target
  - Real-time updates as targets move

**STATUS** (`/data` - `templates/data.html`)
- **Header Controls:** Same unified controls
- **Live Simulator Status:**
  - Current position (lat/lon)
  - Speed Over Ground and Course Over Ground
  - Wind data (when enabled)
  - Simulation time
  - Network configuration (UDP/TCP addresses and ports)
- **GNSS Satellite View:**
  - Sky plot showing satellite positions (azimuth/elevation)
  - SNR (Signal-to-Noise Ratio) bar chart for each satellite
  - DOP values (PDOP, HDOP, VDOP)
  - Count of satellites in view vs. used in solution
- **TCP Clients:**
  - List of connected TCP clients with address:port
  - Connection timestamps
  - Auto-updates as clients connect/disconnect
- **Live NMEA/AIS Console:**
  - Scrolling display of last 200 NMEA sentences
  - Real-time updates as data is generated
  - Shows all sentence types (GPRMC, GPGGA, GPVTG, GSA, GSV, wind, AIS, sensors)

### Static Assets

Located in `static/`:
- **`js/regatta_nmea_simulator.js`** — Main SIMULATOR page logic (map initialization, form handling, GPX upload, slider control, API calls)
- **`js/header_controls.js`** — Shared header controls across all pages (start/stop/reset, running timer, status polling)
- **`js/app.js`** — Additional shared functionality (if present)
- **`css/styles.css`** — Complete styling (layout, theme switching, controls, animations, responsive design)
- **`skippers.txt`** — List of realistic vessel/skipper names used for AIS target naming

## REST API Reference

All endpoints accept and return JSON.

### `GET /api/status`

Returns the current state of the simulator.

**Response:**
```json
{
  "running": bool,
  "host": "127.0.0.1",
  "port": 10110,
  "tcp_host": "0.0.0.0",
  "tcp_port": 10111,
  "interval": 1.0,
  "wind_enabled": bool,
  "heading_enabled": bool,
  "depth_enabled": bool,
  "water_temp_enabled": bool,
  "battery_enabled": bool,
  "air_temp_enabled": bool,
  "tanks_enabled": bool,
  "lat": 42.7157,
  "lon": 16.2321,
  "sog": 5.0,
  "cog": 185.0,
  "tws": 10.0,
  "twd": 270.0,
  "magvar": -2.5,
  "depth_m": 12.0,
  "water_temp_c": 18.0,
  "battery_v": 12.7,
  "air_temp_c": 23.0,
  "tank_fresh_water": 75.0,
  "tank_fuel": 60.0,
  "tank_waste": 30.0,
  "sim_time": "2025-01-01T12:00:00+00:00",
  "started_at": "2025-01-01T12:00:00+00:00",
  "gnss": {
    "sats_in_view": 12,
    "sats_used": 8,
    "pdop": 2.1,
    "hdop": 1.2,
    "vdop": 1.8,
    "satellites": [
      {"prn": 5, "elev": 45, "az": 180, "snr": 42, "used": true},
      ...
    ]
  },
  "ais": {
    "num_targets": 20,
    "targets": [
      {
        "mmsi": 999000001,
        "lat": 42.72,
        "lon": 16.25,
        "sog": 5.5,
        "cog": 190,
        "name": "Alex Smith",
        "display_name": "Alex Smith (SOG 5.5 kn, COG 190°)"
      },
      ...
    ]
  },
  "tcp_clients": [
    {"address": "192.168.1.100:54321", "connected_at": "2025-01-01T12:00:00Z"}
  ],
  "stream_size": 200,
  "gpx_track_info": {
    "points": 1250,
    "start_time": "2025-01-01T10:00:00+00:00",
    "end_time": "2025-01-01T14:30:00+00:00",
    "duration_s": 16200,
    "has_time": true,
    "progress": {
      "mode": "time",
      "offset_s": 3600,
      "sim_time": "2025-01-01T11:00:00+00:00"
    }
  }
}
```

### `GET /api/stream?limit=100`

Returns recent NMEA/AIS sentences from the stream buffer.

**Query Parameters:**
- `limit` (optional, default 100): Maximum number of sentences to return

**Response:**
```json
{
  "lines": [
    "$GPRMC,120000.00,A,4242.9461,N,01613.9304,E,5.0,185.0,010125,2.5,W*6A",
    "$GPGGA,120000.00,4242.9461,N,01613.9304,E,1,08,1.2,10.0,M,0.0,M,,*47",
    ...
  ]
}
```

### `POST /api/start`

Starts the simulator with specified parameters.

**Request Body:** (all fields optional with defaults)
```json
{
  "host": "127.0.0.1",
  "port": 10110,
  "tcp_host": "0.0.0.0",
  "tcp_port": 10111,
  "interval": 1.0,
  "start_datetime": "2025-01-01T12:00:00Z",
  "lat": 42.7157,
  "lon": 16.2321,
  "sog": 5.0,
  "cog": 185.0,
  "magvar": -2.5,
  "wind_enabled": true,
  "tws": 10.0,
  "twd": 270.0,
  "heading_enabled": false,
  "depth_enabled": false,
  "depth_m": 12.0,
  "depth_offset_m": 0.3,
  "water_temp_enabled": false,
  "water_temp_c": 18.0,
  "battery_enabled": false,
  "battery_v": 12.7,
  "air_temp_enabled": false,
  "air_temp_c": 23.0,
  "tanks_enabled": false,
  "tank_fresh_water": 75.0,
  "tank_fuel": 60.0,
  "tank_waste": 30.0,
  "ais_num_targets": 20,
  "ais_max_cog_offset": 20.0,
  "ais_max_sog_offset": 2.0,
  "ais_distribution_radius_nm": 10.0,
  "gpx_id": "uuid-from-upload",
  "gpx_offset_s": 3600,
  "gpx_start_fraction": 0.5
}
```

**Notes:**
- UDP `host` of `0.0.0.0` or empty string is normalized to `127.0.0.1`
- `start_datetime` accepts ISO8601 format; if timezone omitted, UTC is assumed
- For GPX playback: provide `gpx_id` (from upload) and either:
  - `gpx_offset_s`: seconds offset from GPX start time (for tracks with timestamps)
  - `gpx_start_fraction`: 0.0-1.0 position along track (for tracks without timestamps)
- Set `tcp_port` to `null` or `0` to disable TCP server

**Response:**
```json
{
  "ok": true,
  "status": { ... }  // Same as GET /api/status
}
```

**Error Response:**
```json
{
  "ok": false,
  "error": "Simulator already running"
}
```

### `POST /api/stop`

Stops the running simulator.

**Response:**
```json
{
  "ok": true,
  "status": { ... }
}
```

### `POST /api/restart`

Stops the simulator (if running) and starts with new parameters. Accepts same request body as `/api/start`.

**Response:** Same as `/api/start`

### `POST /api/upload_gpx`

Uploads a GPX file for track playback.

**Request:** `multipart/form-data` with `file` field

**Response:**
```json
{
  "ok": true,
  "gpx": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "filename": "track.gpx",
    "saved_path": "uploads/gpx/550e8400-e29b-41d4-a716-446655440000_track.gpx",
    "points_count": 1250,
    "length_nm": 25.5,
    "has_time": true,
    "start_time": "2025-01-01T10:00:00+00:00",
    "end_time": "2025-01-01T14:30:00+00:00",
    "duration_s": 16200,
    "bbox": {
      "minlat": 42.7,
      "maxlat": 42.8,
      "minlon": 16.2,
      "maxlon": 16.3
    },
    "path": [[42.7157, 16.2321], ...],  // Downsampled to ~500 points for map
    "timeline": [[0, 42.7157, 16.2321], [60, 42.7160, 16.2325], ...]  // Time-position samples for slider
  }
}
```

**Error Response:**
```json
{
  "ok": false,
  "error": "Invalid GPX: XML parsing error"
}
```

## NMEASimulator Class

**Location:** `nmea_simulator.py`

The core simulator class that generates and broadcasts NMEA sentences over UDP and TCP.

### Constructor Parameters

```python
NMEASimulator(
  # Network
  host="127.0.0.1",              # UDP destination address
  port=10110,                    # UDP destination port
  tcp_host="0.0.0.0",            # TCP server bind address (0.0.0.0 = all interfaces)
  tcp_port=10111,                # TCP server port (None to disable)
  
  # Timing
  interval=1.0,                  # Update interval in seconds
  start_datetime=None,           # Starting datetime (UTC), None = use real-time
  
  # Position & Navigation
  start_lat=42.715769,           # Starting latitude (decimal degrees)
  start_lon=16.232174,           # Starting longitude (decimal degrees)
  sog_knots=5.0,                 # Speed Over Ground (knots)
  cog_degrees=185.0,             # Course Over Ground (degrees true)
  mag_variation=-2.5,            # Magnetic variation (degrees, E=+ / W=-)
  
  # Wind (optional)
  wind_enabled=True,             # Enable wind sentences
  tws_knots=10.0,                # True Wind Speed (knots)
  twd_degrees=270.0,             # True Wind Direction (degrees true)
  
  # Heading (optional)
  heading_enabled=False,         # Enable HCHDT sentence (derived from COG)
  
  # Depth (optional)
  depth_enabled=False,           # Enable depth sentences
  depth_m=12.0,                  # Water depth (meters)
  depth_offset_m=0.3,            # Transducer offset (meters)
  
  # Water Temperature (optional)
  water_temp_enabled=False,      # Enable water temp sentence
  water_temp_c=18.0,             # Water temperature (°C)
  
  # Battery (optional)
  battery_enabled=False,         # Enable battery voltage sentence
  battery_v=12.7,                # Battery voltage (volts)
  
  # Air Temperature (optional)
  air_temp_enabled=False,        # Enable air temp sentence
  air_temp_c=23.0,               # Air temperature (°C)
  
  # Tank Levels (optional)
  tanks_enabled=False,           # Enable tank level sentences
  tank_fresh_water=75.0,         # Fresh water tank (%)
  tank_fuel=60.0,                # Fuel tank (%)
  tank_waste=30.0,               # Waste water tank (%)
  
  # AIS
  ais_num_targets=0,             # Number of AIS targets to simulate
  ais_max_cog_offset=20.0,       # Max COG offset for targets (degrees)
  ais_max_sog_offset=2.0,        # Max SOG offset for targets (knots)
  ais_distribution_radius_nm=1.0,# Spatial distribution radius (nautical miles)
  
  # GPX Playback (optional)
  gpx_track=None,                # List of track points [{lat, lon, time}, ...]
  gpx_start_fraction=None,       # Starting fraction (0-1) for tracks without timestamps
)
```

### Methods

- **`start()`** — Starts the background simulation thread and begins emitting NMEA data
- **`stop(timeout=5.0)`** — Stops the simulation thread gracefully with optional timeout
- **`restart(**kwargs)`** — Stops the simulator, updates parameters, and restarts
- **`is_running()`** — Returns True if the simulator is currently running
- **`status()`** — Returns dict with current state:
  - `running`, `host`, `port`, `tcp_host`, `tcp_port`
  - `lat`, `lon`, `sog`, `cog`, `tws`, `twd`, `magvar`
  - `sim_time`, `started_at` (ISO8601 timestamps)
  - `wind_enabled`, `heading_enabled`, sensor enable states
  - Sensor values: `depth_m`, `water_temp_c`, `battery_v`, `air_temp_c`, tank levels
  - `gnss`: satellite data (count, DOP values, individual satellites)
  - `ais`: target count and list of targets with positions/speeds
  - `tcp_clients`: list of connected TCP clients
  - `gpx_track_info`: GPX metadata and playback progress
  - `stream_size`: number of buffered NMEA lines
- **`get_stream(limit=100)`** — Returns list of most recent NMEA sentences (up to limit)

### Output Sentences (per interval tick)

**Core GNSS Sentences (always emitted):**
- `$GPRMC` — Recommended Minimum Navigation Information (time, position, SOG, COG, date, magnetic variation)
- `$GPGGA` — Global Positioning System Fix Data (time, position, fix quality, satellites used, HDOP, altitude)
- `$GPVTG` — Track Made Good and Ground Speed (COG true/magnetic, SOG in knots/km/h)
- `$GPGSA` — DOP and Active Satellites (fix type, PRNs of satellites used, PDOP, HDOP, VDOP)
- `$GPGSV` — Satellites in View (multiple sentences showing PRN, elevation, azimuth, SNR for each satellite)

**Wind Sentences (when `wind_enabled=True`):**
- `$WIMWD` — Wind Direction and Speed (true and magnetic wind direction, speed in knots and m/s)
- `$WIMWV` (True) — Wind Speed and Angle (true wind angle relative to bow, speed)
- `$WIMWV` (Apparent) — Wind Speed and Angle (apparent wind angle, speed)

**Heading Sentence (when `heading_enabled=True`):**
- `$HCHDT` — Heading True (true heading derived from COG)

**Depth Sentences (when `depth_enabled=True`):**
- `$SDDPT` — Depth of Water (depth in meters with transducer offset)
- `$SDDBT` — Depth Below Transducer (depth in feet, meters, and fathoms)

**Environmental Sensor Sentences:**
- `$WIMTW` — Water Temperature (when `water_temp_enabled=True`)
- `$IIXDR` (Voltage) — Battery Voltage (when `battery_enabled=True`)
- `$IIXDR` (Temperature) — Air Temperature (when `air_temp_enabled=True`)
- `$IIXDR` (Volume) — Tank Levels (when `tanks_enabled=True`) - separate sentences for FreshWater, Fuel, WasteWater

**AIS Sentences (when `ais_num_targets > 0`):**
- `!AIVDM` Type 18 — Class B Position Report (for each target, each interval)
- `!AIVDM` Type 24 Part A — Static Data Report (vessel name with embedded SOG/COG, sent once per minute for each target)

### Simulation Behavior

The simulator provides realistic evolution of all parameters:

- **Position:** Updates based on SOG and COG using geodetic calculations
- **SOG/COG:** Random walk variations (±0.2 kn, ±2°) to simulate natural movement
- **Wind:** TWS and TWD vary randomly (±0.3 kn, ±3°) over time
- **Sensors:** All sensor values undergo small random variations to simulate real conditions
- **Tank Levels:** Gradually decrease over time (fresh water and fuel consumed, waste increases)
- **GNSS:** Simulates 8-14 satellites in view with realistic SNR values (20-48 dB), computed DOPs
- **AIS Targets:** 
  - Move independently with offsets from main vessel
  - Follow main vessel in manual mode or GPX track in GPX mode
  - Apply configurable spatial (lateral offset) and speed/course variations
  - Names loaded from `static/skippers.txt` or generated algorithmically

### GPX Track Playback

When a GPX track is loaded:

- **Time-based mode** (tracks with timestamps):
  - Simulator time advances and position is interpolated along the track
  - AIS targets follow with temporal offsets (±30-300 seconds based on track duration)
  - Precise alignment to slider position for accurate preview
  
- **Index-based mode** (tracks without timestamps):
  - Position advances through track points at rate determined by SOG and segment distances
  - AIS targets follow with point index offsets (±50 points)
  - Slider uses fractional position (0.0 to 1.0) along track

- **Automatic SOG/COG calculation:** Derived from segment distances and durations (or distances for non-timed tracks)

## Map Tiles and Themes

The web UI supports day and night themes with appropriate map tile sets:

### Light Theme (Day Mode)
- **Base Layer:** Standard OpenStreetMap tiles
- **Overlay:** OpenSeaMap for nautical features (buoys, lights, depth contours, seamarks)
- **UI:** Light color scheme optimized for daylight viewing

### Dark Theme (Night Mode)
- **Base Layer:** Carto "Dark Matter" tiles (OSM-derived dark theme)
- **Overlay:** OpenSeaMap (same overlay works well with both themes)
- **UI:** Dark color scheme with reduced brightness for night sailing/operation

### Features
- Seamless theme switching via toggle button in navigation bar
- Theme preference persists in browser local storage
- Map tiles automatically swap when theme changes
- Leaflet attribution control hidden for cleaner interface
- All maps include OpenSeaMap overlay with maritime information

**Note:** If redistributing this application, review the terms of service for OpenStreetMap, Carto, and OpenSeaMap tile providers.

## Troubleshooting

### Flask server fails to start
**Error:** "Port 5080 is in use" or "Address already in use"

**Solution:** Run on a different port using the `PORT` environment variable:
```bash
PORT=5090 .venv/bin/python nmea_simulator_flask.py
```

### No NMEA data received by consumer application
**Possible causes:**
1. **Wrong UDP port:** Ensure your consumer listens on the same port as configured (default: 10110)
2. **UDP destination `0.0.0.0`:** The simulator normalizes this to `127.0.0.1`
3. **Firewall blocking:** Local firewall may block UDP/TCP traffic
   - On macOS: Check System Preferences → Security & Privacy → Firewall
   - On Linux: Check `iptables` or `ufw` rules
4. **Wrong network interface:** If sending to remote host, ensure network connectivity

**Debugging:**
```bash
# Listen for UDP packets on port 10110
nc -ul 10110

# Or use tcpdump
sudo tcpdump -i lo0 -n udp port 10110 -A
```

### TCP clients can't connect
**Possible causes:**
1. **TCP server disabled:** Ensure `tcp_port` is set to a valid port number (not 0 or null)
2. **Wrong interface:** `tcp_host` must be reachable from client
   - `0.0.0.0` = all interfaces (recommended for external clients)
   - `127.0.0.1` = localhost only
3. **Firewall blocking:** Check firewall rules for TCP port (default: 10111)

**Testing TCP connection:**
```bash
# Test connection to TCP server
telnet localhost 10111

# Or use netcat
nc localhost 10111
```

### GPX file upload fails
**Possible causes:**
1. **Invalid XML:** GPX file must be valid XML
2. **Missing track points:** GPX must contain at least 2 track points
3. **File size:** Very large GPX files may timeout (adjust Flask settings if needed)

**Verification:**
- Check GPX file is valid XML and follows GPX 1.0/1.1 schema
- Ensure `<trkpt>` elements have `lat` and `lon` attributes

### AIS targets not appearing
**Possible causes:**
1. **AIS target count set to 0:** Check AIS configuration and set `ais_num_targets > 0`
2. **Distribution radius too small:** Targets may be very close to main vessel
3. **Map zoom level:** Zoom out to see targets distributed around main vessel

### Simulation not starting
**Check browser console** (F12) for JavaScript errors

**Check Flask logs** for Python exceptions

**Verify status:**
```bash
curl http://localhost:5080/api/status
```

### High CPU usage
The simulator is designed to run efficiently at 1 Hz (one update per second). If experiencing high CPU:
- Increase `interval` value (e.g., 2.0 for updates every 2 seconds)
- Reduce number of AIS targets
- Reduce GPX track resolution (downsample before uploading)

## Project Structure

```
regatta_nmea_simulator/
├── nmea_simulator.py              # Core NMEASimulator class and CLI entry point
├── nmea_simulator_flask.py        # Flask web server with REST API
├── requirements.txt               # Python dependencies (Flask)
├── README.md                      # This file
├── templates/                     # Jinja2 HTML templates
│   ├── index.html                 # Main SIMULATOR page
│   ├── ais.html                   # AIS targets configuration and visualization
│   └── data.html                  # STATUS page with live data
├── static/                        # Static assets (CSS, JavaScript, data)
│   ├── css/
│   │   └── styles.css             # Complete application styling
│   ├── js/
│   │   ├── regatta_nmea_simulator.js  # Main page logic (map, GPX, controls)
│   │   ├── header_controls.js     # Shared header controls across pages
│   │   └── app.js                 # Additional shared functionality
│   └── skippers.txt               # List of vessel/skipper names for AIS
├── uploads/                       # Created at runtime
│   └── gpx/                       # Uploaded GPX files stored here
└── __pycache__/                   # Python bytecode cache

Key Files:
- nmea_simulator.py: 1200+ lines, pure Python NMEA generator with threading
- nmea_simulator_flask.py: Flask routes, API endpoints, GPX processing
- static/js/regatta_nmea_simulator.js: 1200+ lines, main UI logic
- templates/index.html: 350+ lines, main simulator interface
```

### Component Responsibilities

**nmea_simulator.py**
- NMEA sentence generation (all types: GNSS, wind, sensors, AIS)
- Simulation logic (position updates, random variations)
- UDP and TCP networking
- GPX track playback
- AIS target management
- Thread-safe status reporting

**nmea_simulator_flask.py**
- Flask application setup and routing
- REST API implementation
- GPX file upload and parsing
- Coordinate system transformations
- Session management

**Static Assets**
- `regatta_nmea_simulator.js`: Map initialization, user input handling, API communication
- `header_controls.js`: Start/Stop/Reset buttons, running timer, status polling
- `styles.css`: Complete styling including themes, animations, responsive layout
- `skippers.txt`: Realistic vessel names for AIS simulation

## License

MIT License

Copyright (c) 2025 Christian Heiling

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

---

## Use Cases

This simulator is ideal for:

- **Marine Software Development:** Test navigation apps, chart plotters, and instrument displays without needing physical devices or being on the water
- **Integration Testing:** Validate NMEA 0183 parsing and data handling in marine electronics projects
- **Education:** Learn about NMEA protocols, GPS/GNSS systems, AIS, and marine navigation
- **UI/UX Design:** Develop and test user interfaces for marine applications with realistic data streams
- **Fleet Simulation:** Test multi-vessel scenarios with configurable AIS targets
- **Route Planning:** Simulate GPX tracks to verify routing algorithms and navigation logic
- **Demo and Training:** Demonstrate marine software capabilities with realistic, controllable data

## Contributing

Contributions are welcome! Please feel free to submit issues, feature requests, or pull requests.

## Acknowledgments

- OpenStreetMap contributors for map tiles
- Carto for Dark Matter theme tiles
- OpenSeaMap for nautical overlay data
- Leaflet.js for mapping library
- Flask framework for web backend

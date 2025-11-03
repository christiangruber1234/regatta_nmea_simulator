# NMEA 0183 Simulator

Lightweight NMEA 0183 UDP simulator for testing marine software without a boat. It generates realistic GPS and wind sentences and broadcasts them to a configurable host and port.

## What it does

- Sends a continuous stream of NMEA 0183 sentences over UDP:
  - GPS: GPRMC, GPGGA, GPVTG
  - Wind (optional): WIMWD, WIMWV (True and Apparent)
- Simulates gradual changes in position, speed over ground (SOG), course over ground (COG), wind speed, and wind direction.
- Lets you disable wind instruments to simulate sensor loss.

## Requirements

- Python 3.8+ (standard library only; no external packages required)

## Run the simulator (CLI)

1. Open a terminal and go to the project folder.
2. Start the generator:

  macOS / Linux:
  ```bash
  python3 nmea_simulator.py
  ```

  Windows:
  ```bash
  py nmea_simulator.py
  ```

By default it sends to 127.0.0.1:10110 once per second. Point your consumer (e.g., OpenCPN, Expedition, custom app) to listen on that UDP port.

### Configuration

Edit the top of `nmea_simulator.py` to change:

- `TARGET_HOST` (default `127.0.0.1`)
- `TARGET_PORT` (default `10110`)
- `SEND_INTERVAL` seconds (default `1.0`)
- `WIND_INSTRUMENTS_ENABLED` boolean (default `False`)

## Web UI (Flask)

A simple responsive Flask app provides a control panel and a map to set the starting position.

- Day/Night mode (persisted in localStorage)
- Start/Stop/Restart the simulator
- Choose starting position using OpenStreetMap (Leaflet). Click or drag the marker.
- Choose starting date and time (UTC) via a datetime picker

Run it locally:

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python nmea_simulator_flask.py
```

Then open http://localhost:5080 in your browser.

## Project layout

- `nmea_simulator.py` — UDP NMEA simulator script (also importable NMEASimulator class)
- `nmea_simulator_flask.py` — Flask server exposing a web UI and REST API
- `templates/index.html`, `static/js/app.js`, `static/css/styles.css` — Web UI assets
- `requirements.txt` — Python deps for the web app

All other polar-performance and GUI tools have been removed in this repository; this project now only contains the NMEA simulator.

## License

MIT License. See the repository for details.

### Support the project

If this simulator helps you, you can support development here: [Donate via PayPal](https://paypal.me/ChristianHeiling).

# REST API Reference

All endpoints accept and return JSON.

## Endpoints

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

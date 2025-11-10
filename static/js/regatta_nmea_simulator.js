/* Frontend logic for NMEA Simulator UI */

const html = document.documentElement;
const themeBtn = document.getElementById('themeBtn');
const hostEl = document.getElementById('host');
const portEl = document.getElementById('port');
const tcpPortEl = document.getElementById('tcp_port');
const tcpHostEl = document.getElementById('tcp_host');
const intervalEl = document.getElementById('interval');
const windSelectEl = document.getElementById('wind_enabled'); // legacy
const windToggleEl = document.getElementById('wind_enabled_toggle');
const windFieldsEl = document.getElementById('wind_fields');
const latEl = document.getElementById('lat');
const lonEl = document.getElementById('lon');
const startDtEl = document.getElementById('start_datetime');
const sogEl = document.getElementById('sog');
const cogEl = document.getElementById('cog');
const twsEl = document.getElementById('tws');
const twdEl = document.getElementById('twd');
const magvarEl = document.getElementById('magvar');
const headingEnabledEl = document.getElementById('heading_enabled');
const headingFieldsEl = document.getElementById('heading_fields');
const statusText = document.getElementById('statusText');

// Sensor elements
const depthEnabledEl = document.getElementById('depth_enabled');
const depthFieldsEl = document.getElementById('depth_fields');
const depthMEl = document.getElementById('depth_m');
const depthOffsetMEl = document.getElementById('depth_offset_m');
const waterTempEnabledEl = document.getElementById('water_temp_enabled');
const waterTempFieldsEl = document.getElementById('water_temp_fields');
const waterTempCEl = document.getElementById('water_temp_c');
const batteryEnabledEl = document.getElementById('battery_enabled');
const batteryFieldsEl = document.getElementById('battery_fields');
const batteryVEl = document.getElementById('battery_v');
const airTempEnabledEl = document.getElementById('air_temp_enabled');
const airTempFieldsEl = document.getElementById('air_temp_fields');
const airTempCEl = document.getElementById('air_temp_c');
const tanksEnabledEl = document.getElementById('tanks_enabled');
const tanksFieldsEl = document.getElementById('tanks_fields');
const tankFreshWaterEl = document.getElementById('tank_fresh_water');
const tankFuelEl = document.getElementById('tank_fuel');
const tankWasteEl = document.getElementById('tank_waste');

const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const resetBtn = document.getElementById('resetBtn');
const updateBtn = document.getElementById('updateBtn');
const initModeToggle = document.getElementById('init_mode_toggle');
const initModeEl = document.getElementById('init_mode'); // legacy select if present
const gpxFileEl = document.getElementById('gpx_file');
const gpxMetaEl = document.getElementById('gpxMeta');
const gpxFilenameBar = document.getElementById('gpxFilenameBar');
const manualParams = document.getElementById('manual_params');
const gpxParams = document.getElementById('gpx_params');
const intervalGpxEl = document.getElementById('interval_gpx');
let currentGpxId = null;
let gpxPolyline = null;
function fitGpxBounds(){
  try{
    if (gpxPolyline){
      const b = gpxPolyline.getBounds();
      if (b && b.isValid()){
        map.fitBounds(b, { padding: [20,20] });
      }
    } else if (currentGpxMeta && Array.isArray(currentGpxMeta.path) && currentGpxMeta.path.length > 1){
      const b = L.latLngBounds(currentGpxMeta.path.map(p => [p[0], p[1]]));
      map.fitBounds(b, { padding: [20,20] });
    }
  }catch(e){ /* ignore */ }
}
let currentGpxMeta = null;
let gpxSliderEl = document.getElementById('gpx_slider');
let gpxCursorLabel = document.getElementById('gpxCursorLabel');
let gpxSelectedOffsetS = 0; // seconds from GPX start when time data exists
let gpxSelectedFraction = 0; // 0..1 when no time
// Running timer
let runningTicker = null;
let simStartedAtMs = null;

function zero2(n){ return String(n).padStart(2, '0'); }
function formatHMS(ms){
  const totalSec = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  return `${zero2(h)}:${zero2(m)}:${zero2(s)}`;
}
function updateStartButtonLabelTick(){
  if (!startBtn) return;
  if (simStartedAtMs && !isNaN(simStartedAtMs)){
    const diff = Date.now() - simStartedAtMs;
    startBtn.textContent = `▶ RUNNING ${formatHMS(diff)}`;
  } else {
    startBtn.textContent = '▶ RUNNING';
  }
}

// Theme toggle
const savedTheme = localStorage.getItem('theme') || 'dark';
html.setAttribute('data-theme', savedTheme);
function updateThemeIcon(){
  const isDark = html.getAttribute('data-theme') === 'dark';
  if (themeBtn) themeBtn.textContent = isDark ? '🌙' : '☀️';
}
updateThemeIcon();
if (themeBtn) {
  themeBtn.addEventListener('click', () => {
    const isDark = html.getAttribute('data-theme') === 'dark';
    const t = isDark ? 'light' : 'dark';
    html.setAttribute('data-theme', t);
    localStorage.setItem('theme', t);
    updateThemeIcon();
    // Switch map tiles to match theme
    map.removeLayer(currentTiles);
    currentTiles = (t === 'dark') ? darkTiles : lightTiles;
    currentTiles.addTo(map);
  });
}

// Set default Start Date & Time (UTC) on load if empty
function pad2(n){ return String(n).padStart(2, '0'); }
function setDefaultStartUTC(){
  if (!startDtEl.value) {
    const now = new Date();
    const y = now.getUTCFullYear();
    const m = pad2(now.getUTCMonth() + 1);
    const d = pad2(now.getUTCDate());
    const hh = pad2(now.getUTCHours());
    const mm = pad2(now.getUTCMinutes());
    // datetime-local expects YYYY-MM-DDTHH:MM
    startDtEl.value = `${y}-${m}-${d}T${hh}:${mm}`;
  }
}
setDefaultStartUTC();

// Leaflet map (hide attribution footer)
const map = L.map('map', { attributionControl: false }).setView([parseFloat(latEl.value), parseFloat(lonEl.value)], 10);

// Define base layers and OpenSeaMap seamark overlay
const lightTiles = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: 'Map data: &copy; OpenStreetMap contributors | Nautical data: &copy; OpenSeaMap'
});

// CARTO Dark Matter (note: third-party terms may apply)
const darkTiles = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
  maxZoom: 19,
  attribution: 'Map data: &copy; OpenStreetMap contributors, &copy; CARTO | Nautical data: &copy; OpenSeaMap'
});

// OpenSeaMap seamarks overlay
const seamarkTiles = L.tileLayer('https://tiles.openseamap.org/seamark/{z}/{x}/{y}.png', {
  maxZoom: 19,
  opacity: 0.9,
  zIndex: 10,
});

let currentTiles = (savedTheme === 'dark') ? darkTiles : lightTiles;
currentTiles.addTo(map);
seamarkTiles.addTo(map);

let marker = L.marker([parseFloat(latEl.value), parseFloat(lonEl.value)], {
  draggable: true,
  zIndexOffset: 1000,
  opacity: 0
}).addTo(map);
let currentMarker = null; // simulator current position when running
let aisMarkers = new Map(); // mmsi -> {marker, directionLine} for AIS targets

// Boat heading marker
let boatMarker = null;
let boatHeadingMarker = null; // boat triangle showing COG
let windArrowMarker = null; // wind arrow showing TWD

// Create boat heading icon (triangle)
function createBoatIcon(cog) {
  const svg = `<svg width="80" height="80" xmlns="http://www.w3.org/2000/svg">
    <g transform="translate(40,40) rotate(${cog})">
      <line x1="0" y1="-15" x2="0" y2="-35" stroke="#3b82f6" stroke-width="2"/>
      <path d="M 0,-15 L 8,12 L 0,8 L -8,12 Z" fill="#3b82f6" stroke="#1e40af" stroke-width="2"/>
    </g>
  </svg>`;
  return L.divIcon({
    html: svg,
    className: 'boat-icon',
    iconSize: [80, 80],
    iconAnchor: [40, 40]
  });
}

// Create wind arrow icon - arrow points TO the boat (wind coming FROM direction)
function createWindIcon(twd, tws) {
  const svg = `<svg width="160" height="160" xmlns="http://www.w3.org/2000/svg">
    <g transform="translate(80,80) rotate(${twd})">
      <line x1="0" y1="-60" x2="0" y2="25" stroke="#ffffff" stroke-width="3"/>
      <polygon points="0,25 -6,15 6,15" fill="#ffffff"/>
      <circle cx="0" cy="-60" r="3" fill="#ffffff"/>
      <g transform="translate(0,-60)">
        <rect x="-25" y="-25" width="50" height="20" fill="rgba(0,0,0,0.8)" rx="4"/>
        <text x="0" y="-8" font-size="13" fill="#ffffff" font-weight="bold" text-anchor="middle">${Math.round(tws)}kn</text>
      </g>
    </g>
  </svg>`;
  return L.divIcon({
    html: svg,
    className: 'wind-icon',
    iconSize: [160, 160],
    iconAnchor: [80, 80]
  });
}

// Update boat heading marker
function updateBoatHeading() {
  const lat = parseFloat(latEl.value);
  const lon = parseFloat(lonEl.value);
  const cog = parseFloat(cogEl.value) || 0;
  
  if (isNaN(lat) || isNaN(lon)) return;
  
  if (!boatHeadingMarker) {
    boatHeadingMarker = L.marker([lat, lon], {
      icon: createBoatIcon(cog),
      interactive: false,
      zIndexOffset: 100
    }).addTo(map);
  } else {
    boatHeadingMarker.setLatLng([lat, lon]);
    boatHeadingMarker.setIcon(createBoatIcon(cog));
  }
}

// Update wind arrow marker
function updateWindArrow() {
  const lat = parseFloat(latEl.value);
  const lon = parseFloat(lonEl.value);
  const twd = parseFloat(twdEl.value) || 0;
  const tws = parseFloat(twsEl.value) || 0;
  const windEnabled = windToggleEl && windToggleEl.checked;
  
  if (!windEnabled || isNaN(lat) || isNaN(lon)) {
    if (windArrowMarker) {
      map.removeLayer(windArrowMarker);
      windArrowMarker = null;
    }
    return;
  }
  
  if (!windArrowMarker) {
    windArrowMarker = L.marker([lat, lon], {
      icon: createWindIcon(twd, tws),
      interactive: false,
      zIndexOffset: 50
    }).addTo(map);
  } else {
    windArrowMarker.setLatLng([lat, lon]);
    windArrowMarker.setIcon(createWindIcon(twd, tws));
  }
}

// Calculate end point for AIS direction line
// Returns [lat, lon] for a point at distance_nm in direction cog_degrees from origin
function calculateDirectionEndpoint(lat, lon, cog_degrees, distance_nm) {
  const R = 6371.0; // Earth radius in km
  const d = distance_nm * 1.852; // Convert nm to km
  const bearing = cog_degrees * Math.PI / 180.0; // Convert to radians
  const lat1 = lat * Math.PI / 180.0;
  const lon1 = lon * Math.PI / 180.0;
  
  const lat2 = Math.asin(
    Math.sin(lat1) * Math.cos(d / R) +
    Math.cos(lat1) * Math.sin(d / R) * Math.cos(bearing)
  );
  
  const lon2 = lon1 + Math.atan2(
    Math.sin(bearing) * Math.sin(d / R) * Math.cos(lat1),
    Math.cos(d / R) - Math.sin(lat1) * Math.sin(lat2)
  );
  
  return [lat2 * 180.0 / Math.PI, lon2 * 180.0 / Math.PI];
}

// Initial update
updateBoatHeading();
updateWindArrow();

function syncInputsFromMarker(){
  const {lat, lng} = marker.getLatLng();
  latEl.value = lat.toFixed(6);
  lonEl.value = lng.toFixed(6);
  updateBoatHeading();
  updateWindArrow();
  
  // If simulator is running, send live update to move boat and AIS targets
  if (isSimulatorRunning) {
    // Show visual feedback that position is being updated
    if (statusText) {
      const prevText = statusText.textContent;
      statusText.textContent = 'Updating position...';
      statusText.style.color = '#3b82f6';
      setTimeout(() => {
        statusText.textContent = prevText;
        statusText.style.color = '';
      }, 1500);
    }
    handleFieldChange('lat');
    handleFieldChange('lon');
  }
}
marker.on('dragend', syncInputsFromMarker);
map.on('click', (e) => {
  marker.setLatLng(e.latlng);
  syncInputsFromMarker();
});

// Add listeners to update boat heading and wind arrow
if (cogEl) cogEl.addEventListener('input', updateBoatHeading);
if (twdEl) twdEl.addEventListener('input', updateWindArrow);
if (twsEl) twsEl.addEventListener('input', updateWindArrow);
if (windToggleEl) windToggleEl.addEventListener('change', updateWindArrow);

// TWD wraparound: if value goes above 359, wrap to 0
if (twdEl) {
  twdEl.addEventListener('input', function() {
    let val = parseFloat(twdEl.value);
    if (!isNaN(val)) {
      if (val > 359) {
        twdEl.value = 0;
      } else if (val < 0) {
        twdEl.value = 359;
      }
    }
  });
}

// Mode toggle for Initial parameters
function getInitMode(){
  if (initModeToggle) return initModeToggle.checked ? 'gpx' : 'manual';
  if (initModeEl) return initModeEl.value;
  return 'manual';
}
function setInitMode(mode){
  if (initModeToggle){ initModeToggle.checked = (mode === 'gpx'); }
  if (initModeEl){ initModeEl.value = mode; }
}
function updateInitModeUI(){
  const mode = getInitMode();
  if (mode === 'gpx'){
    if (manualParams) manualParams.style.display = 'none';
    if (gpxParams) gpxParams.style.display = '';
    // When switching into GPX mode, zoom to full track if available
    fitGpxBounds();
  }else{
    if (manualParams) manualParams.style.display = '';
    if (gpxParams) gpxParams.style.display = 'none';
  }
}
if (initModeEl){ initModeEl.addEventListener('change', () => { updateInitModeUI(); persistUiState(); }); }
if (initModeToggle){ initModeToggle.addEventListener('change', () => { updateInitModeUI(); persistUiState(); }); }
updateInitModeUI();

// Upload GPX
async function uploadGpx(file){
  const fd = new FormData();
  fd.append('file', file);
  const res = await fetch('/api/upload_gpx', { method: 'POST', body: fd });
  const data = await res.json();
  if(!res.ok){ throw new Error(data.error || 'Upload failed'); }
  const g = data.gpx;
  currentGpxId = g.id;
  currentGpxMeta = g;
  // Persist GPX selection and meta for page reloads
  try { localStorage.setItem('gpx.currentId', currentGpxId); } catch(e){}
  try { localStorage.setItem('gpx.currentMeta', JSON.stringify(currentGpxMeta)); } catch(e){}
  try { localStorage.setItem('gpx.filename', g.filename || ''); } catch(e){}
  if (gpxFilenameBar){ gpxFilenameBar.textContent = g.filename ? `File: ${g.filename}` : 'File: (unnamed)'; }
  if (gpxMetaEl){
    const dur = (g.duration_s != null) ? `${Math.floor(g.duration_s/3600)}h ${Math.floor((g.duration_s%3600)/60)}m ${g.duration_s%60}s` : 'n/a';
    gpxMetaEl.innerHTML = `
      <ul>
        <li>File: <b>${g.filename || '(unnamed)'}</b></li>
        <li>Points: <b>${g.points_count}</b></li>
        <li>Length: <b>${g.length_nm} nm</b></li>
        <li>Has time: <b>${g.has_time ? 'Yes' : 'No'}</b></li>
        <li>Start: <b>${g.start_time || 'n/a'}</b></li>
        <li>End: <b>${g.end_time || 'n/a'}</b></li>
        <li>Duration: <b>${dur}</b></li>
      </ul>`;
  }
  // Prepare slider
  if (gpxSliderEl){
    if (g.has_time && typeof g.duration_s === 'number'){
      gpxSliderEl.min = 0; gpxSliderEl.max = g.duration_s; gpxSliderEl.step = 1; gpxSliderEl.value = 0; gpxSelectedOffsetS = 0;
    } else {
      // Use path length for index-based slider
      const maxIdx = Math.max(0, (g.path || []).length - 1);
      gpxSliderEl.min = 0; gpxSliderEl.max = maxIdx; gpxSliderEl.step = 1; gpxSliderEl.value = 0; gpxSelectedFraction = 0;
    }
    updateGpxSliderPreview();
  }
  // Draw polyline and fit bounds
  try{
    if (gpxPolyline){ map.removeLayer(gpxPolyline); gpxPolyline = null; }
    if (Array.isArray(g.path) && g.path.length > 1){
      gpxPolyline = L.polyline(g.path.map(p => [p[0], p[1]]), { color: '#22d3ee', weight: 3, opacity: 0.8 }).addTo(map);
      fitGpxBounds();
      // Move the draggable marker to the start point for context
      const [slat, slon] = g.path[0];
      marker.setLatLng([slat, slon]);
      syncInputsFromMarker();
    }
  }catch(e){ /* ignore */ }
}
if (gpxFileEl){
  gpxFileEl.addEventListener('change', () => {
    const f = gpxFileEl.files && gpxFileEl.files[0];
    if (f){ uploadGpx(f).catch(err => alert(err.message)); }
  });
}

function lerp(a,b,t){ return a + (b-a)*t; }
function updateGpxSliderPreview(){
  if(!currentGpxMeta || !Array.isArray(currentGpxMeta.path) || currentGpxMeta.path.length === 0) return;
  const path = currentGpxMeta.path;
  if (currentGpxMeta.has_time && typeof currentGpxMeta.duration_s === 'number'){
    const t = parseInt(gpxSliderEl.value, 10) || 0;
    gpxSelectedOffsetS = t;
    // Position preview: use precise time-based timeline if available
    let lat, lon;
    const timeline = Array.isArray(currentGpxMeta.timeline) ? currentGpxMeta.timeline : null;
    if (timeline && timeline.length > 1){
      // Binary search for bracket around t
      let lo = 0, hi = timeline.length - 1;
      if (t <= timeline[0][0]){
        lat = timeline[0][1]; lon = timeline[0][2];
      } else if (t >= timeline[hi][0]){
        lat = timeline[hi][1]; lon = timeline[hi][2];
      } else {
        while (hi - lo > 1){
          const mid = (lo + hi) >> 1;
          if (timeline[mid][0] <= t) lo = mid; else hi = mid;
        }
        const t0 = timeline[lo][0], t1 = timeline[hi][0];
        const f = (t - t0) / Math.max(1, (t1 - t0));
        lat = lerp(timeline[lo][1], timeline[hi][1], f);
        lon = lerp(timeline[lo][2], timeline[hi][2], f);
      }
    } else {
      // Fallback: fraction of time over downsampled path
      const frac = Math.max(0, Math.min(1, t / Math.max(1, currentGpxMeta.duration_s)));
      const idxF = frac * Math.max(1, path.length - 1);
      const i0 = Math.floor(idxF), i1 = Math.min(path.length - 1, i0 + 1);
      const f = idxF - i0;
      const [lat0, lon0] = path[i0];
      const [lat1, lon1] = path[i1];
      lat = lerp(lat0, lat1, f);
      lon = lerp(lon0, lon1, f);
    }
    marker.setLatLng([lat, lon]);
    syncInputsFromMarker();
    if (gpxCursorLabel){
      const start = currentGpxMeta.start_time ? new Date(currentGpxMeta.start_time) : null;
      const ts = start ? new Date(start.getTime() + t*1000).toISOString() : `+${t}s`;
      gpxCursorLabel.textContent = `Selected: ${ts}`;
    }
  } else {
    const idx = parseInt(gpxSliderEl.value, 10) || 0;
    const i0 = Math.max(0, Math.min(path.length - 1, idx));
    const [lat, lon] = path[i0];
    marker.setLatLng([lat, lon]);
    syncInputsFromMarker();
    gpxSelectedFraction = (path.length > 1) ? (i0 / (path.length - 1)) : 0;
    if (gpxCursorLabel){ gpxCursorLabel.textContent = `Selected path index: ${i0}/${path.length-1}`; }
  }
}

if (gpxSliderEl){ gpxSliderEl.addEventListener('input', updateGpxSliderPreview); }

// Persist UI mode and slider changes
function persistUiState(){
  try { localStorage.setItem('ui.initMode', getInitMode()); } catch(e){}
  try { localStorage.setItem('gpx.selectedOffsetS', String(gpxSelectedOffsetS || 0)); } catch(e){}
  try { localStorage.setItem('gpx.selectedFraction', String(gpxSelectedFraction || 0)); } catch(e){}
}
if (initModeEl){ initModeEl.addEventListener('change', persistUiState); }
if (gpxSliderEl){ gpxSliderEl.addEventListener('change', persistUiState); }

// Rehydrate from persisted state on load
function restorePersisted(){
  try {
  const savedMode = localStorage.getItem('ui.initMode');
  if (savedMode){ setInitMode(savedMode); updateInitModeUI(); }
    const savedMeta = localStorage.getItem('gpx.currentMeta');
    const savedId = localStorage.getItem('gpx.currentId');
    const savedFilename = localStorage.getItem('gpx.filename');
    if (savedMeta){
      const g = JSON.parse(savedMeta);
      currentGpxMeta = g; currentGpxId = savedId || g.id;
      if (gpxFilenameBar){ gpxFilenameBar.textContent = savedFilename ? `File: ${savedFilename}` : 'No GPX selected.'; }
      // Render meta block
      if (gpxMetaEl){
        const dur = (g.duration_s != null) ? `${Math.floor(g.duration_s/3600)}h ${Math.floor((g.duration_s%3600)/60)}m ${g.duration_s%60}s` : 'n/a';
        gpxMetaEl.innerHTML = `
          <ul>
            <li>File: <b>${g.filename || '(unnamed)'}</b></li>
            <li>Points: <b>${g.points_count}</b></li>
            <li>Length: <b>${g.length_nm} nm</b></li>
            <li>Has time: <b>${g.has_time ? 'Yes' : 'No'}</b></li>
            <li>Start: <b>${g.start_time || 'n/a'}</b></li>
            <li>End: <b>${g.end_time || 'n/a'}</b></li>
            <li>Duration: <b>${dur}</b></li>
          </ul>`;
      }
      // Recreate polyline and slider
      if (gpxPolyline){ map.removeLayer(gpxPolyline); gpxPolyline = null; }
      if (Array.isArray(g.path) && g.path.length > 1){
        gpxPolyline = L.polyline(g.path.map(p => [p[0], p[1]]), { color: '#22d3ee', weight: 3, opacity: 0.8 }).addTo(map);
        fitGpxBounds();
      }
      if (gpxSliderEl){
        if (g.has_time && typeof g.duration_s === 'number'){
          gpxSliderEl.min = 0; gpxSliderEl.max = g.duration_s; gpxSliderEl.step = 1;
          const so = parseInt(localStorage.getItem('gpx.selectedOffsetS') || '0', 10);
          gpxSliderEl.value = isNaN(so) ? 0 : so; gpxSelectedOffsetS = parseInt(gpxSliderEl.value, 10) || 0;
        } else {
          const maxIdx = Math.max(0, (g.path || []).length - 1);
          gpxSliderEl.min = 0; gpxSliderEl.max = maxIdx; gpxSliderEl.step = 1;
          const sf = parseFloat(localStorage.getItem('gpx.selectedFraction') || '0');
          const i0 = Math.max(0, Math.min(maxIdx, Math.round(sf * (maxIdx || 1))));
          gpxSliderEl.value = String(i0);
          gpxSelectedFraction = maxIdx ? (i0 / maxIdx) : 0;
        }
        updateGpxSliderPreview();
      }
    }
  } catch(e){}
}
restorePersisted();

// API helpers
async function api(method, path, body){
  const res = await fetch(path, { method, headers: {'Content-Type': 'application/json'}, body: body ? JSON.stringify(body) : undefined });
  const data = await res.json();
  if(!res.ok){ throw new Error(data.error || 'Request failed'); }
  return data;
}

async function refreshStatus(){
  try {
    const data = await api('GET', '/api/status');
    const running = !!data.running;
    
    // Track running state and show/hide update button
    const wasRunning = isSimulatorRunning;
    isSimulatorRunning = running;
    
    // Sync UI with actual simulator state (enabled/disabled toggles and current values)
    // Skip fields that were recently updated by the user to prevent overwriting their changes
    if (running && data) {
      // Update Starting Conditions panel - skip if recently updated
      if (typeof data.lat === 'number' && latEl && !recentlyUpdatedFields.has('lat')) {
        latEl.value = data.lat.toFixed(6);
      }
      if (typeof data.lon === 'number' && lonEl && !recentlyUpdatedFields.has('lon')) {
        lonEl.value = data.lon.toFixed(6);
      }
      if (typeof data.interval === 'number' && intervalEl && !recentlyUpdatedFields.has('interval')) {
        intervalEl.value = data.interval;
      }
      if (typeof data.interval === 'number' && intervalGpxEl && !recentlyUpdatedFields.has('interval_gpx')) {
        intervalGpxEl.value = data.interval;
      }
      if (data.sim_time && startDtEl && !recentlyUpdatedFields.has('start_datetime')) {
        // Convert UTC time string to local datetime-local format
        try {
          const utcDate = new Date(data.sim_time);
          if (!isNaN(utcDate.getTime())) {
            // Format as YYYY-MM-DDTHH:MM:SS for datetime-local input
            const year = utcDate.getFullYear();
            const month = String(utcDate.getMonth() + 1).padStart(2, '0');
            const day = String(utcDate.getDate()).padStart(2, '0');
            const hours = String(utcDate.getHours()).padStart(2, '0');
            const minutes = String(utcDate.getMinutes()).padStart(2, '0');
            const seconds = String(utcDate.getSeconds()).padStart(2, '0');
            startDtEl.value = `${year}-${month}-${day}T${hours}:${minutes}:${seconds}`;
          }
        } catch(e) {}
      }
      
      // Update enable/disable toggles - skip if recently updated
      if (headingEnabledEl && headingEnabledEl.checked !== data.heading_enabled && !recentlyUpdatedFields.has('heading_enabled')) {
        headingEnabledEl.checked = data.heading_enabled;
      }
      if (depthEnabledEl && depthEnabledEl.checked !== data.depth_enabled && !recentlyUpdatedFields.has('depth_enabled')) {
        depthEnabledEl.checked = data.depth_enabled;
        updateDepthUI();
      }
      if (waterTempEnabledEl && waterTempEnabledEl.checked !== data.water_temp_enabled && !recentlyUpdatedFields.has('water_temp_enabled')) {
        waterTempEnabledEl.checked = data.water_temp_enabled;
        updateWaterTempUI();
      }
      if (batteryEnabledEl && batteryEnabledEl.checked !== data.battery_enabled && !recentlyUpdatedFields.has('battery_enabled')) {
        batteryEnabledEl.checked = data.battery_enabled;
        updateBatteryUI();
      }
      if (airTempEnabledEl && airTempEnabledEl.checked !== data.air_temp_enabled && !recentlyUpdatedFields.has('air_temp_enabled')) {
        airTempEnabledEl.checked = data.air_temp_enabled;
        updateAirTempUI();
      }
      if (tanksEnabledEl && tanksEnabledEl.checked !== data.tanks_enabled && !recentlyUpdatedFields.has('tanks_enabled')) {
        tanksEnabledEl.checked = data.tanks_enabled;
        updateTanksUI();
      }
      if (windToggleEl && windToggleEl.checked !== data.wind_enabled && !recentlyUpdatedFields.has('wind_enabled_toggle')) {
        windToggleEl.checked = data.wind_enabled;
        updateWindUI();
      }
      
      // Update current values from simulator - skip if recently updated
      if (typeof data.sog === 'number' && sogEl && !recentlyUpdatedFields.has('sog')) {
        sogEl.value = data.sog.toFixed(1);
      }
      if (typeof data.cog === 'number' && cogEl && !recentlyUpdatedFields.has('cog')) {
        cogEl.value = Math.round(data.cog);
      }
      if (typeof data.tws === 'number' && twsEl && !recentlyUpdatedFields.has('tws')) {
        twsEl.value = data.tws.toFixed(1);
      }
      if (typeof data.twd === 'number' && twdEl && !recentlyUpdatedFields.has('twd')) {
        twdEl.value = Math.round(data.twd);
      }
      if (typeof data.magvar === 'number' && magvarEl && !recentlyUpdatedFields.has('magvar')) {
        magvarEl.value = data.magvar;
      }
      if (typeof data.depth_m === 'number' && depthMEl && !recentlyUpdatedFields.has('depth_m')) {
        depthMEl.value = data.depth_m.toFixed(1);
      }
      if (typeof data.depth_offset_m === 'number' && depthOffsetMEl && !recentlyUpdatedFields.has('depth_offset_m')) {
        depthOffsetMEl.value = data.depth_offset_m.toFixed(1);
      }
      if (typeof data.water_temp_c === 'number' && waterTempCEl && !recentlyUpdatedFields.has('water_temp_c')) {
        waterTempCEl.value = data.water_temp_c.toFixed(1);
      }
      if (typeof data.battery_v === 'number' && batteryVEl && !recentlyUpdatedFields.has('battery_v')) {
        batteryVEl.value = data.battery_v.toFixed(1);
      }
      if (typeof data.air_temp_c === 'number' && airTempCEl && !recentlyUpdatedFields.has('air_temp_c')) {
        airTempCEl.value = data.air_temp_c.toFixed(1);
      }
      if (typeof data.tank_fresh_water === 'number' && tankFreshWaterEl && !recentlyUpdatedFields.has('tank_fresh_water')) {
        tankFreshWaterEl.value = data.tank_fresh_water.toFixed(1);
      }
      if (typeof data.tank_fuel === 'number' && tankFuelEl && !recentlyUpdatedFields.has('tank_fuel')) {
        tankFuelEl.value = data.tank_fuel.toFixed(1);
      }
      if (typeof data.tank_waste === 'number' && tankWasteEl && !recentlyUpdatedFields.has('tank_waste')) {
        tankWasteEl.value = data.tank_waste.toFixed(1);
      }
      
      // Update map markers with current values
      updateBoatHeading();
      updateWindArrow();
    }
    
    if (statusText) {
      statusText.textContent = running ? `Status: Running (lat=${(data.lat||0).toFixed?.(4)}, lon=${(data.lon||0).toFixed?.(4)}, port=${data.port})` : 'Status: Stopped';
    }
    startBtn.disabled = running;
    // Update Start button label to show uptime as HH:MM:SS and animate border while running
    try {
      if (running) {
        // Determine start time from backend or fallback to local storage
        if (data.started_at) {
          const st = new Date(data.started_at);
          simStartedAtMs = st.getTime();
        } else {
          let startedAt = parseInt(localStorage.getItem('sim.startedAtEpoch') || '0', 10);
          if (!startedAt || isNaN(startedAt)) {
            startedAt = Date.now();
            localStorage.setItem('sim.startedAtEpoch', String(startedAt));
          }
          simStartedAtMs = startedAt;
        }
        // Ensure per-second ticker is running
        if (!runningTicker) {
          runningTicker = setInterval(updateStartButtonLabelTick, 1000);
        }
        // Immediate label update
        updateStartButtonLabelTick();
        // Apply running style
        startBtn.classList.add('btn-running');
      } else {
        // Clear ticker and reset label/styles
        if (runningTicker) { clearInterval(runningTicker); runningTicker = null; }
        simStartedAtMs = null;
        startBtn.textContent = '▶ Start';
        startBtn.classList.remove('btn-running');
        try { localStorage.removeItem('sim.startedAtEpoch'); } catch(e){}
      }
    } catch(e){}
    stopBtn.disabled = !running;
    // Visual state on header buttons
    try {
      if (running) {
        startBtn.classList.remove('btn-green');
        stopBtn.classList.add('btn-red');
      } else {
        stopBtn.classList.remove('btn-red');
        startBtn.classList.add('btn-green');
      }
    } catch(e){}
    // Update current position marker on map when running
    if (running && typeof data.lat === 'number' && typeof data.lon === 'number') {
      const latLng = [data.lat, data.lon];
      if (!currentMarker) {
        currentMarker = L.circleMarker(latLng, { radius: 6, color: '#ff3860', fillColor: '#ff3860', fillOpacity: 0.9 }).addTo(map);
      } else {
        currentMarker.setLatLng(latLng);
      }
    } else {
      if (currentMarker) {
        map.removeLayer(currentMarker);
        currentMarker = null;
      }
    }

    // Update AIS targets on map when running
    if (running && data.ais && data.ais.targets) {
      const ais = data.ais.targets || [];
      const seen = new Set();
      for (const t of ais) {
        seen.add(String(t.mmsi));
        const latLng = [t.lat, t.lon];
        const cog = t.cog || 0;
        const sog = t.sog || 0;
        
        // Calculate direction line endpoint (length proportional to SOG, min 0.5nm, max 2nm)
        const lineLength = Math.min(2.0, Math.max(0.5, sog * 0.2));
        const endPoint = calculateDirectionEndpoint(t.lat, t.lon, cog, lineLength);
        
        let aisData = aisMarkers.get(String(t.mmsi));
        if (!aisData) {
          // Create new marker and direction line
          const marker = L.circleMarker(latLng, { 
            radius: 5, 
            color: '#1e90ff', 
            fillColor: '#1e90ff', 
            fillOpacity: 0.9 
          }).addTo(map);
          marker.bindTooltip(`${t.display_name || (t.name || 'Vessel')}\nMMSI ${t.mmsi}`);
          
          const directionLine = L.polyline([latLng, endPoint], {
            color: '#1e90ff',
            weight: 2,
            opacity: 0.7
          }).addTo(map);
          
          aisMarkers.set(String(t.mmsi), { marker, directionLine });
        } else {
          // Update existing marker and direction line
          aisData.marker.setLatLng(latLng);
          aisData.marker.setTooltipContent(`${t.display_name || (t.name || 'Vessel')}\nMMSI ${t.mmsi}`);
          aisData.directionLine.setLatLngs([latLng, endPoint]);
        }
      }
      // Remove stale markers and lines
      for (const [k, aisData] of aisMarkers) {
        if (!seen.has(k)) {
          map.removeLayer(aisData.marker);
          map.removeLayer(aisData.directionLine);
          aisMarkers.delete(k);
        }
      }
    } else {
      // Clear all AIS markers and direction lines when stopped
      for (const [k, aisData] of aisMarkers) {
        map.removeLayer(aisData.marker);
        map.removeLayer(aisData.directionLine);
      }
      aisMarkers.clear();
    }

    // Sync GPX slider to simulation progress when running
    if (running && currentGpxMeta && gpxSliderEl && data.gpx_track_info){
      const gi = data.gpx_track_info;
      const prog = gi.progress || {};
      if (gi.has_time && typeof currentGpxMeta.duration_s === 'number' && prog.mode === 'time' && typeof prog.offset_s === 'number'){
        const off = Math.max(0, Math.min(currentGpxMeta.duration_s, prog.offset_s));
        if (String(gpxSliderEl.value) !== String(off)){
          gpxSliderEl.value = String(off); gpxSelectedOffsetS = off; updateGpxSliderPreview(); persistUiState();
        }
      } else if (!gi.has_time && Array.isArray(currentGpxMeta.path) && currentGpxMeta.path.length > 1 && prog.mode === 'index'){
        const maxIdx = currentGpxMeta.path.length - 1;
        const idx = Math.max(0, Math.min(maxIdx, Math.round((prog.fraction || 0) * maxIdx)));
        if (String(gpxSliderEl.value) !== String(idx)){
          gpxSliderEl.value = String(idx); gpxSelectedFraction = maxIdx ? (idx / maxIdx) : 0; updateGpxSliderPreview(); persistUiState();
        }
      }
    }
  } catch (e) {
    if (statusText) { statusText.textContent = 'Status: Unknown'; }
  }
}

async function start(){
  const body = {
    host: hostEl.value,
    port: parseInt(portEl.value, 10),
    tcp_port: parseInt(tcpPortEl.value, 10),
    tcp_host: tcpHostEl ? tcpHostEl.value : '0.0.0.0',
  interval: parseFloat((getInitMode()==='gpx' ? intervalGpxEl.value : intervalEl.value)),
  wind_enabled: getWindEnabled(),
    heading_enabled: headingEnabledEl ? !!headingEnabledEl.checked : false,
    depth_enabled: depthEnabledEl ? !!depthEnabledEl.checked : false,
    depth_m: depthMEl ? parseFloat(depthMEl.value) : 12.0,
    depth_offset_m: depthOffsetMEl ? parseFloat(depthOffsetMEl.value) : 0.3,
    water_temp_enabled: waterTempEnabledEl ? !!waterTempEnabledEl.checked : false,
    water_temp_c: waterTempCEl ? parseFloat(waterTempCEl.value) : 18.0,
    battery_enabled: batteryEnabledEl ? !!batteryEnabledEl.checked : false,
    battery_v: batteryVEl ? parseFloat(batteryVEl.value) : 12.5,
    air_temp_enabled: airTempEnabledEl ? !!airTempEnabledEl.checked : false,
    air_temp_c: airTempCEl ? parseFloat(airTempCEl.value) : 20.0,
    tanks_enabled: tanksEnabledEl ? !!tanksEnabledEl.checked : false,
    tank_fresh_water: tankFreshWaterEl ? parseFloat(tankFreshWaterEl.value) : 80.0,
    tank_fuel: tankFuelEl ? parseFloat(tankFuelEl.value) : 60.0,
    tank_waste: tankWasteEl ? parseFloat(tankWasteEl.value) : 15.0,
    lat: parseFloat(latEl.value),
    lon: parseFloat(lonEl.value),
    start_datetime: startDtEl.value ? new Date(startDtEl.value).toISOString() : null,
    sog: parseFloat(sogEl.value),
    cog: parseFloat(cogEl.value),
    tws: parseFloat(twsEl.value),
    twd: parseFloat(twdEl.value),
    magvar: parseFloat(magvarEl.value),
  };
  // Add AIS parameters
  const aisEnabledEl = document.getElementById('ais_enabled');
  const aisNumEl = document.getElementById('ais_num_targets');
  const aisCogEl = document.getElementById('ais_max_cog_offset');
  const aisSogEl = document.getElementById('ais_max_sog_offset');
  const aisRadiusEl = document.getElementById('ais_distribution_radius_nm');
  if (aisEnabledEl) body.ais_enabled = !!aisEnabledEl.checked;
  if (aisNumEl) body.ais_num_targets = parseInt(aisNumEl.value, 10);
  if (aisCogEl) body.ais_max_cog_offset = parseFloat(aisCogEl.value);
  if (aisSogEl) body.ais_max_sog_offset = parseFloat(aisSogEl.value);
  if (aisRadiusEl) body.ais_distribution_radius_nm = parseFloat(aisRadiusEl.value);
  
  if (getInitMode()==='gpx' && currentGpxId){
    body.gpx_id = currentGpxId;
    if (currentGpxMeta && currentGpxMeta.has_time){ body.gpx_offset_s = gpxSelectedOffsetS; }
    else { body.gpx_start_fraction = gpxSelectedFraction; }
  }
  await api('POST', '/api/start', body);
  await refreshStatus();
  if (window.updateHeaderButtonState) await window.updateHeaderButtonState();
}

async function stop(){
  await api('POST', '/api/stop', {});
  await refreshStatus();
  if (window.updateHeaderButtonState) await window.updateHeaderButtonState();
}

async function restart(){
  const body = {
    host: hostEl.value,
    port: parseInt(portEl.value, 10),
    tcp_port: parseInt(tcpPortEl.value, 10),
    tcp_host: tcpHostEl ? tcpHostEl.value : '0.0.0.0',
  interval: parseFloat((getInitMode()==='gpx' ? intervalGpxEl.value : intervalEl.value)),
  wind_enabled: getWindEnabled(),
    heading_enabled: headingEnabledEl ? !!headingEnabledEl.checked : false,
    depth_enabled: depthEnabledEl ? !!depthEnabledEl.checked : false,
    depth_m: depthMEl ? parseFloat(depthMEl.value) : 12.0,
    depth_offset_m: depthOffsetMEl ? parseFloat(depthOffsetMEl.value) : 0.3,
    water_temp_enabled: waterTempEnabledEl ? !!waterTempEnabledEl.checked : false,
    water_temp_c: waterTempCEl ? parseFloat(waterTempCEl.value) : 18.0,
    battery_enabled: batteryEnabledEl ? !!batteryEnabledEl.checked : false,
    battery_v: batteryVEl ? parseFloat(batteryVEl.value) : 12.5,
    air_temp_enabled: airTempEnabledEl ? !!airTempEnabledEl.checked : false,
    air_temp_c: airTempCEl ? parseFloat(airTempCEl.value) : 20.0,
    tanks_enabled: tanksEnabledEl ? !!tanksEnabledEl.checked : false,
    tank_fresh_water: tankFreshWaterEl ? parseFloat(tankFreshWaterEl.value) : 80.0,
    tank_fuel: tankFuelEl ? parseFloat(tankFuelEl.value) : 60.0,
    tank_waste: tankWasteEl ? parseFloat(tankWasteEl.value) : 15.0,
    lat: parseFloat(latEl.value),
    lon: parseFloat(lonEl.value),
    start_datetime: startDtEl.value ? new Date(startDtEl.value).toISOString() : null,
    sog: parseFloat(sogEl.value),
    cog: parseFloat(cogEl.value),
    tws: parseFloat(twsEl.value),
    twd: parseFloat(twdEl.value),
    magvar: parseFloat(magvarEl.value),
  };
  // Add AIS parameters
  const aisEnabledEl = document.getElementById('ais_enabled');
  const aisNumEl = document.getElementById('ais_num_targets');
  const aisCogEl = document.getElementById('ais_max_cog_offset');
  const aisSogEl = document.getElementById('ais_max_sog_offset');
  const aisRadiusEl = document.getElementById('ais_distribution_radius_nm');
  if (aisEnabledEl) body.ais_enabled = !!aisEnabledEl.checked;
  if (aisNumEl) body.ais_num_targets = parseInt(aisNumEl.value, 10);
  if (aisCogEl) body.ais_max_cog_offset = parseFloat(aisCogEl.value);
  if (aisSogEl) body.ais_max_sog_offset = parseFloat(aisSogEl.value);
  if (aisRadiusEl) body.ais_distribution_radius_nm = parseFloat(aisRadiusEl.value);
  
  if (getInitMode()==='gpx' && currentGpxId){
    body.gpx_id = currentGpxId;
    if (currentGpxMeta && currentGpxMeta.has_time){ body.gpx_offset_s = gpxSelectedOffsetS; }
    else { body.gpx_start_fraction = gpxSelectedFraction; }
  }
  await api('POST', '/api/restart', body);
  await refreshStatus();
  if (window.updateHeaderButtonState) await window.updateHeaderButtonState();
}

async function resetToDefaults() {
  // Stop simulator if running
  if (isSimulatorRunning) {
    await stop();
  }
  
  // Reset all fields to their default values
  if (latEl) latEl.value = '42.715769349296004';
  if (lonEl) lonEl.value = '16.23217374761267';
  if (startDtEl) startDtEl.value = '';
  if (intervalEl) intervalEl.value = '1.0';
  if (intervalGpxEl) intervalGpxEl.value = '1.0';
  if (sogEl) sogEl.value = '5';
  if (cogEl) cogEl.value = '185';
  if (twsEl) twsEl.value = '10';
  if (twdEl) twdEl.value = '270';
  if (magvarEl) magvarEl.value = '-2.5';
  
  // Reset toggles
  if (windToggleEl) { windToggleEl.checked = true; updateWindUI(); }
  if (headingEnabledEl) { headingEnabledEl.checked = true; updateHeadingUI(); }
  
  // Reset auxiliary sensors
  if (depthEnabledEl) { depthEnabledEl.checked = true; updateDepthUI(); }
  if (depthMEl) depthMEl.value = '12.0';
  if (depthOffsetMEl) depthOffsetMEl.value = '0.3';
  
  if (waterTempEnabledEl) { waterTempEnabledEl.checked = true; updateWaterTempUI(); }
  if (waterTempCEl) waterTempCEl.value = '18.0';
  
  if (batteryEnabledEl) { batteryEnabledEl.checked = true; updateBatteryUI(); }
  if (batteryVEl) batteryVEl.value = '12.7';
  
  if (airTempEnabledEl) { airTempEnabledEl.checked = true; updateAirTempUI(); }
  if (airTempCEl) airTempCEl.value = '20.0';
  
  if (tanksEnabledEl) { tanksEnabledEl.checked = true; updateTanksUI(); }
  if (tankFreshWaterEl) tankFreshWaterEl.value = '75';
  if (tankFuelEl) tankFuelEl.value = '60';
  if (tankWasteEl) tankWasteEl.value = '30';
  
  // Reset AIS
  const aisEnabledEl = document.getElementById('ais_enabled');
  const aisNumEl = document.getElementById('ais_num_targets');
  const aisCogEl = document.getElementById('ais_max_cog_offset');
  const aisSogEl = document.getElementById('ais_max_sog_offset');
  const aisRadiusEl = document.getElementById('ais_distribution_radius_nm');
  if (aisEnabledEl) { aisEnabledEl.checked = true; updateAisUI(); }
  if (aisNumEl) aisNumEl.value = '20';
  if (aisCogEl) aisCogEl.value = '20';
  if (aisSogEl) aisSogEl.value = '2.0';
  if (aisRadiusEl) aisRadiusEl.value = '10.0';
  
  // Reset network settings
  if (hostEl) hostEl.value = 'localhost';
  if (portEl) portEl.value = '10110';
  if (tcpPortEl) tcpPortEl.value = '10111';
  if (tcpHostEl) tcpHostEl.value = '0.0.0.0';
  
  // Update map markers
  updateBoatHeading();
  updateWindArrow();
  
  // Reset map view to default position
  if (map && latEl && lonEl) {
    map.setView([parseFloat(latEl.value), parseFloat(lonEl.value)], 10);
    if (marker) {
      marker.setLatLng([parseFloat(latEl.value), parseFloat(lonEl.value)]);
    }
  }
}

// Track if simulator is running and recently updated fields
let isSimulatorRunning = false;
let recentlyUpdatedFields = new Set(); // Track fields that were just updated by user
let updateTimeouts = new Map(); // Debounce timeouts for each field

// Flash the running badge green when update is sent
function flashRunningBadge() {
  if (startBtn && startBtn.classList.contains('btn-running')) {
    startBtn.style.transition = 'background-color 0.3s ease';
    const originalBg = startBtn.style.backgroundColor;
    startBtn.style.backgroundColor = '#22c55e'; // green-500
    setTimeout(() => {
      startBtn.style.backgroundColor = originalBg;
      setTimeout(() => {
        startBtn.style.transition = '';
      }, 300);
    }, 300);
  }
}

// Send live update to simulator when a value changes
async function sendLiveUpdate() {
  if (!isSimulatorRunning) return;
  
  const body = {
    host: hostEl.value,
    port: parseInt(portEl.value, 10),
    tcp_port: parseInt(tcpPortEl.value, 10),
    tcp_host: tcpHostEl ? tcpHostEl.value : '0.0.0.0',
    interval: parseFloat((getInitMode()==='gpx' ? intervalGpxEl.value : intervalEl.value)),
    wind_enabled: getWindEnabled(),
    heading_enabled: headingEnabledEl ? !!headingEnabledEl.checked : false,
    depth_enabled: depthEnabledEl ? !!depthEnabledEl.checked : false,
    depth_m: depthMEl ? parseFloat(depthMEl.value) : 12.0,
    depth_offset_m: depthOffsetMEl ? parseFloat(depthOffsetMEl.value) : 0.3,
    water_temp_enabled: waterTempEnabledEl ? !!waterTempEnabledEl.checked : false,
    water_temp_c: waterTempCEl ? parseFloat(waterTempCEl.value) : 18.0,
    battery_enabled: batteryEnabledEl ? !!batteryEnabledEl.checked : false,
    battery_v: batteryVEl ? parseFloat(batteryVEl.value) : 12.5,
    air_temp_enabled: airTempEnabledEl ? !!airTempEnabledEl.checked : false,
    air_temp_c: airTempCEl ? parseFloat(airTempCEl.value) : 20.0,
    tanks_enabled: tanksEnabledEl ? !!tanksEnabledEl.checked : false,
    tank_fresh_water: tankFreshWaterEl ? parseFloat(tankFreshWaterEl.value) : 80.0,
    tank_fuel: tankFuelEl ? parseFloat(tankFuelEl.value) : 60.0,
    tank_waste: tankWasteEl ? parseFloat(tankWasteEl.value) : 15.0,
    lat: parseFloat(latEl.value),
    lon: parseFloat(lonEl.value),
    start_datetime: startDtEl.value ? new Date(startDtEl.value).toISOString() : null,
    sog: parseFloat(sogEl.value),
    cog: parseFloat(cogEl.value),
    tws: parseFloat(twsEl.value),
    twd: parseFloat(twdEl.value),
    magvar: parseFloat(magvarEl.value),
  };
  
  // Add AIS parameters
  const aisEnabledEl = document.getElementById('ais_enabled');
  const aisNumEl = document.getElementById('ais_num_targets');
  const aisCogEl = document.getElementById('ais_max_cog_offset');
  const aisSogEl = document.getElementById('ais_max_sog_offset');
  const aisRadiusEl = document.getElementById('ais_distribution_radius_nm');
  if (aisEnabledEl) body.ais_enabled = !!aisEnabledEl.checked;
  if (aisNumEl) body.ais_num_targets = parseInt(aisNumEl.value, 10);
  if (aisCogEl) body.ais_max_cog_offset = parseFloat(aisCogEl.value);
  if (aisSogEl) body.ais_max_sog_offset = parseFloat(aisSogEl.value);
  if (aisRadiusEl) body.ais_distribution_radius_nm = parseFloat(aisRadiusEl.value);
  
  if (getInitMode()==='gpx' && currentGpxId){
    body.gpx_id = currentGpxId;
    if (currentGpxMeta && currentGpxMeta.has_time){ body.gpx_offset_s = gpxSelectedOffsetS; }
    else { body.gpx_start_fraction = gpxSelectedFraction; }
  }
  
  try {
    await api('POST', '/api/restart', body);
    flashRunningBadge();
  } catch(e) {
    console.error('Live update failed:', e);
  }
}

// Handle field changes with debouncing
function handleFieldChange(fieldId) {
  if (!isSimulatorRunning) return;
  
  // Mark this field as recently updated
  recentlyUpdatedFields.add(fieldId);
  
  // Clear any existing timeout for this field
  if (updateTimeouts.has(fieldId)) {
    clearTimeout(updateTimeouts.get(fieldId));
  }
  
  // Set a debounce timeout - wait 500ms after last change before sending update
  const timeout = setTimeout(async () => {
    await sendLiveUpdate();
    // Keep field marked as recently updated for 3 seconds to prevent overwrite during next refresh
    setTimeout(() => {
      recentlyUpdatedFields.delete(fieldId);
    }, 3000);
  }, 500);
  
  updateTimeouts.set(fieldId, timeout);
}

// Add change listeners to all input fields for live updates
function setupLiveUpdates() {
  const inputs = document.querySelectorAll('input, select');
  inputs.forEach(input => {
    // Skip the GPX file input as it triggers different flow
    if (input.id === 'gpx_file') return;
    
    input.addEventListener('change', () => handleFieldChange(input.id));
    input.addEventListener('input', () => {
      // Only handle input events for text-like inputs (not checkboxes/radios)
      if (input.type !== 'checkbox' && input.type !== 'radio') {
        handleFieldChange(input.id);
      }
    });
  });
}

startBtn.addEventListener('click', () => start().catch(err => alert(err.message)));
stopBtn.addEventListener('click', () => stop().catch(err => alert(err.message)));
resetBtn.addEventListener('click', () => resetToDefaults().catch(err => alert(err.message)));

refreshStatus();
setInterval(refreshStatus, 2000);

// Setup live updates after page loads
setupLiveUpdates();

function getWindEnabled(){
  if (windToggleEl) return !!windToggleEl.checked;
  if (windSelectEl) return windSelectEl.value === 'true';
  return true;
}

function updateWindUI(){
  const on = getWindEnabled();
  if (windFieldsEl){ windFieldsEl.style.display = on ? '' : 'none'; }
}
if (windToggleEl){ windToggleEl.addEventListener('change', updateWindUI); }
if (windSelectEl){ windSelectEl.addEventListener('change', updateWindUI); }
updateWindUI();

// Heading UI show/hide
function updateHeadingUI(){
  const on = headingEnabledEl && headingEnabledEl.checked;
  if (headingFieldsEl){ headingFieldsEl.style.display = on ? '' : 'none'; }
}
if (headingEnabledEl){ headingEnabledEl.addEventListener('change', updateHeadingUI); }
updateHeadingUI();

// Sensor UI show/hide
function updateDepthUI(){
  const on = depthEnabledEl && depthEnabledEl.checked;
  if (depthFieldsEl){ depthFieldsEl.style.display = on ? '' : 'none'; }
}
function updateWaterTempUI(){
  const on = waterTempEnabledEl && waterTempEnabledEl.checked;
  if (waterTempFieldsEl){ waterTempFieldsEl.style.display = on ? '' : 'none'; }
}
function updateBatteryUI(){
  const on = batteryEnabledEl && batteryEnabledEl.checked;
  if (batteryFieldsEl){ batteryFieldsEl.style.display = on ? '' : 'none'; }
}
function updateAirTempUI(){
  const on = airTempEnabledEl && airTempEnabledEl.checked;
  if (airTempFieldsEl){ airTempFieldsEl.style.display = on ? '' : 'none'; }
}
function updateTanksUI(){
  const on = tanksEnabledEl && tanksEnabledEl.checked;
  if (tanksFieldsEl){ tanksFieldsEl.style.display = on ? '' : 'none'; }
}
function updateAisUI(){
  const aisEnabledEl = document.getElementById('ais_enabled');
  const aisFieldsEl = document.getElementById('ais_fields');
  const on = aisEnabledEl && aisEnabledEl.checked;
  if (aisFieldsEl){ aisFieldsEl.style.display = on ? '' : 'none'; }
}
if (depthEnabledEl){ depthEnabledEl.addEventListener('change', updateDepthUI); }
if (waterTempEnabledEl){ waterTempEnabledEl.addEventListener('change', updateWaterTempUI); }
if (batteryEnabledEl){ batteryEnabledEl.addEventListener('change', updateBatteryUI); }
if (airTempEnabledEl){ airTempEnabledEl.addEventListener('change', updateAirTempUI); }
if (tanksEnabledEl){ tanksEnabledEl.addEventListener('change', updateTanksUI); }
const aisEnabledEl = document.getElementById('ais_enabled');
if (aisEnabledEl){ aisEnabledEl.addEventListener('change', updateAisUI); }

// Auxiliary Data master toggle - controls all auxiliary sensors
const auxiliaryMasterToggle = document.getElementById('auxiliary_master_toggle');
const auxiliaryPanels = document.getElementById('auxiliary_panels');
if (auxiliaryMasterToggle) {
  auxiliaryMasterToggle.addEventListener('change', function() {
    const isOn = auxiliaryMasterToggle.checked;
    // Show/hide all sub-panels
    if (auxiliaryPanels) {
      auxiliaryPanels.style.display = isOn ? '' : 'none';
    }
    // Toggle all sensor checkboxes
    if (depthEnabledEl) { depthEnabledEl.checked = isOn; updateDepthUI(); }
    if (waterTempEnabledEl) { waterTempEnabledEl.checked = isOn; updateWaterTempUI(); }
    if (batteryEnabledEl) { batteryEnabledEl.checked = isOn; updateBatteryUI(); }
    if (airTempEnabledEl) { airTempEnabledEl.checked = isOn; updateAirTempUI(); }
    if (tanksEnabledEl) { tanksEnabledEl.checked = isOn; updateTanksUI(); }
  });
}

updateDepthUI();
updateWaterTempUI();
updateBatteryUI();
updateAirTempUI();
updateTanksUI();
updateAisUI();


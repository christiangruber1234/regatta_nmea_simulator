/* Frontend logic for NMEA Simulator UI */

const html = document.documentElement;
const themeBtn = document.getElementById('themeBtn');
const hostEl = document.getElementById('host');
const portEl = document.getElementById('port');
const tcpPortEl = document.getElementById('tcp_port');
const tcpHostEl = document.getElementById('tcp_host');
const intervalEl = document.getElementById('interval');
const windEl = document.getElementById('wind_enabled');
const latEl = document.getElementById('lat');
const lonEl = document.getElementById('lon');
const startDtEl = document.getElementById('start_datetime');
const sogEl = document.getElementById('sog');
const cogEl = document.getElementById('cog');
const twsEl = document.getElementById('tws');
const twdEl = document.getElementById('twd');
const magvarEl = document.getElementById('magvar');
const statusText = document.getElementById('statusText');

const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const restartBtn = document.getElementById('restartBtn');
const initModeEl = document.getElementById('init_mode');
const gpxFileEl = document.getElementById('gpx_file');
const gpxMetaEl = document.getElementById('gpxMeta');
const manualParams = document.getElementById('manual_params');
const gpxParams = document.getElementById('gpx_params');
const intervalGpxEl = document.getElementById('interval_gpx');
let currentGpxId = null;
let gpxPolyline = null;
let currentGpxMeta = null;
let gpxSliderEl = document.getElementById('gpx_slider');
let gpxCursorLabel = document.getElementById('gpxCursorLabel');
let gpxSelectedOffsetS = 0; // seconds from GPX start when time data exists
let gpxSelectedFraction = 0; // 0..1 when no time

// Theme toggle
const savedTheme = localStorage.getItem('theme') || 'light';
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

// Leaflet map
const map = L.map('map').setView([parseFloat(latEl.value), parseFloat(lonEl.value)], 10);

// Define light and dark tile layers
const lightTiles = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; OpenStreetMap contributors'
});

// CARTO Dark Matter (note: third-party terms may apply)
const darkTiles = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
  maxZoom: 19,
  attribution: '&copy; OpenStreetMap contributors, &copy; CARTO'
});

let currentTiles = (savedTheme === 'dark') ? darkTiles : lightTiles;
currentTiles.addTo(map);

let marker = L.marker([parseFloat(latEl.value), parseFloat(lonEl.value)], {draggable: true}).addTo(map);
let currentMarker = null; // simulator current position when running

function syncInputsFromMarker(){
  const {lat, lng} = marker.getLatLng();
  latEl.value = lat.toFixed(6);
  lonEl.value = lng.toFixed(6);
}
marker.on('dragend', syncInputsFromMarker);
map.on('click', (e) => {
  marker.setLatLng(e.latlng);
  syncInputsFromMarker();
});

// Mode toggle for Initial parameters
function updateInitModeUI(){
  const mode = initModeEl ? initModeEl.value : 'manual';
  if (mode === 'gpx'){
    if (manualParams) manualParams.style.display = 'none';
    if (gpxParams) gpxParams.style.display = '';
  }else{
    if (manualParams) manualParams.style.display = '';
    if (gpxParams) gpxParams.style.display = 'none';
  }
}
if (initModeEl){ initModeEl.addEventListener('change', updateInitModeUI); updateInitModeUI(); }

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
  if (gpxMetaEl){
    const dur = (g.duration_s != null) ? `${Math.floor(g.duration_s/3600)}h ${Math.floor((g.duration_s%3600)/60)}m ${g.duration_s%60}s` : 'n/a';
    gpxMetaEl.innerHTML = `
      <ul>
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
      const b = L.latLngBounds(g.path.map(p => [p[0], p[1]]));
      map.fitBounds(b, { padding: [20,20] });
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
  try { localStorage.setItem('ui.initMode', initModeEl ? initModeEl.value : 'manual'); } catch(e){}
  try { localStorage.setItem('gpx.selectedOffsetS', String(gpxSelectedOffsetS || 0)); } catch(e){}
  try { localStorage.setItem('gpx.selectedFraction', String(gpxSelectedFraction || 0)); } catch(e){}
}
if (initModeEl){ initModeEl.addEventListener('change', persistUiState); }
if (gpxSliderEl){ gpxSliderEl.addEventListener('change', persistUiState); }

// Rehydrate from persisted state on load
function restorePersisted(){
  try {
    const savedMode = localStorage.getItem('ui.initMode');
    if (savedMode && initModeEl){ initModeEl.value = savedMode; updateInitModeUI(); }
    const savedMeta = localStorage.getItem('gpx.currentMeta');
    const savedId = localStorage.getItem('gpx.currentId');
    if (savedMeta){
      const g = JSON.parse(savedMeta);
      currentGpxMeta = g; currentGpxId = savedId || g.id;
      // Render meta block
      if (gpxMetaEl){
        const dur = (g.duration_s != null) ? `${Math.floor(g.duration_s/3600)}h ${Math.floor((g.duration_s%3600)/60)}m ${g.duration_s%60}s` : 'n/a';
        gpxMetaEl.innerHTML = `
          <ul>
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
        const b = L.latLngBounds(g.path.map(p => [p[0], p[1]]));
        map.fitBounds(b, { padding: [20,20] });
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
    statusText.textContent = running ? `Status: Running (lat=${(data.lat||0).toFixed?.(4)}, lon=${(data.lon||0).toFixed?.(4)}, port=${data.port})` : 'Status: Stopped';
    startBtn.disabled = running;
    stopBtn.disabled = !running;
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
    statusText.textContent = 'Status: Unknown';
  }
}

async function start(){
  const body = {
    host: hostEl.value,
    port: parseInt(portEl.value, 10),
    tcp_port: parseInt(tcpPortEl.value, 10),
    tcp_host: tcpHostEl ? tcpHostEl.value : '0.0.0.0',
    interval: parseFloat((initModeEl && initModeEl.value==='gpx' ? intervalGpxEl.value : intervalEl.value)),
    wind_enabled: windEl.value === 'true',
    lat: parseFloat(latEl.value),
    lon: parseFloat(lonEl.value),
    start_datetime: startDtEl.value ? new Date(startDtEl.value).toISOString() : null,
    sog: parseFloat(sogEl.value),
    cog: parseFloat(cogEl.value),
    tws: parseFloat(twsEl.value),
    twd: parseFloat(twdEl.value),
    magvar: parseFloat(magvarEl.value),
  };
  if (initModeEl && initModeEl.value === 'gpx' && currentGpxId){
    body.gpx_id = currentGpxId;
    if (currentGpxMeta && currentGpxMeta.has_time){ body.gpx_offset_s = gpxSelectedOffsetS; }
    else { body.gpx_start_fraction = gpxSelectedFraction; }
  }
  await api('POST', '/api/start', body);
  await refreshStatus();
}

async function stop(){
  await api('POST', '/api/stop', {});
  await refreshStatus();
}

async function restart(){
  const body = {
    host: hostEl.value,
    port: parseInt(portEl.value, 10),
    tcp_port: parseInt(tcpPortEl.value, 10),
    tcp_host: tcpHostEl ? tcpHostEl.value : '0.0.0.0',
    interval: parseFloat((initModeEl && initModeEl.value==='gpx' ? intervalGpxEl.value : intervalEl.value)),
    wind_enabled: windEl.value === 'true',
    lat: parseFloat(latEl.value),
    lon: parseFloat(lonEl.value),
    start_datetime: startDtEl.value ? new Date(startDtEl.value).toISOString() : null,
    sog: parseFloat(sogEl.value),
    cog: parseFloat(cogEl.value),
    tws: parseFloat(twsEl.value),
    twd: parseFloat(twdEl.value),
    magvar: parseFloat(magvarEl.value),
  };
  if (initModeEl && initModeEl.value === 'gpx' && currentGpxId){
    body.gpx_id = currentGpxId;
    if (currentGpxMeta && currentGpxMeta.has_time){ body.gpx_offset_s = gpxSelectedOffsetS; }
    else { body.gpx_start_fraction = gpxSelectedFraction; }
  }
  await api('POST', '/api/restart', body);
  await refreshStatus();
}

startBtn.addEventListener('click', () => start().catch(err => alert(err.message)));
stopBtn.addEventListener('click', () => stop().catch(err => alert(err.message)));
restartBtn.addEventListener('click', () => restart().catch(err => alert(err.message)));

refreshStatus();
setInterval(refreshStatus, 2000);

/* Frontend logic for NMEA Simulator UI */

const html = document.documentElement;
const themeToggle = document.getElementById('themeToggle');
const themeLabel = document.getElementById('themeLabel');
const hostEl = document.getElementById('host');
const portEl = document.getElementById('port');
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

// Theme toggle
const savedTheme = localStorage.getItem('theme') || 'light';
html.setAttribute('data-theme', savedTheme);
themeToggle.checked = savedTheme === 'dark';
updateThemeLabel();

themeToggle.addEventListener('change', () => {
  const t = themeToggle.checked ? 'dark' : 'light';
  html.setAttribute('data-theme', t);
  localStorage.setItem('theme', t);
  updateThemeLabel();
});

function updateThemeLabel(){
  themeLabel.textContent = themeToggle.checked ? 'Night' : 'Day';
}

// Leaflet map
const map = L.map('map').setView([parseFloat(latEl.value), parseFloat(lonEl.value)], 10);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);
let marker = L.marker([parseFloat(latEl.value), parseFloat(lonEl.value)], {draggable: true}).addTo(map);

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
  } catch (e) {
    statusText.textContent = 'Status: Unknown';
  }
}

async function start(){
  const body = {
    host: hostEl.value,
    port: parseInt(portEl.value, 10),
    interval: parseFloat(intervalEl.value),
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
    interval: parseFloat(intervalEl.value),
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
  await api('POST', '/api/restart', body);
  await refreshStatus();
}

startBtn.addEventListener('click', () => start().catch(err => alert(err.message)));
stopBtn.addEventListener('click', () => stop().catch(err => alert(err.message)));
restartBtn.addEventListener('click', () => restart().catch(err => alert(err.message)));

refreshStatus();
setInterval(refreshStatus, 2000);

(function(){
  const startBtn = document.getElementById('startBtn');
  const stopBtn = document.getElementById('stopBtn');
  const restartBtn = document.getElementById('restartBtn');
  if (!startBtn || !stopBtn || !restartBtn) return; // Header controls not present

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
      startBtn.textContent = `RUNNING ${formatHMS(diff)}`;
    } else {
      startBtn.textContent = 'RUNNING';
    }
  }

  async function api(method, path, body){
    const res = await fetch(path, { method, headers: {'Content-Type': 'application/json'}, body: body ? JSON.stringify(body) : undefined });
    const data = await res.json();
    if(!res.ok){ throw new Error(data.error || 'Request failed'); }
    return data;
  }

  async function refreshHeader(){
    try{
      const data = await api('GET', '/api/status');
      const running = !!data.running;
      // Toggle enable/disable
      startBtn.disabled = running;
      stopBtn.disabled = !running;
      // Update label/timer and animation
      if (running) {
        if (data.started_at){ simStartedAtMs = new Date(data.started_at).getTime(); }
        if (!runningTicker) runningTicker = setInterval(updateStartButtonLabelTick, 1000);
        updateStartButtonLabelTick();
        startBtn.classList.add('btn-running');
        // State colors
        startBtn.classList.remove('btn-green');
        stopBtn.classList.add('btn-red');
      } else {
        if (runningTicker) { clearInterval(runningTicker); runningTicker = null; }
        simStartedAtMs = null;
        startBtn.textContent = 'Start';
        startBtn.classList.remove('btn-running');
        stopBtn.classList.remove('btn-red');
        startBtn.classList.add('btn-green');
      }
    }catch(e){ /* ignore */ }
  }

  async function doStart(){
    try{
      // Minimal start: use server defaults
      await api('POST', '/api/start', {});
      await refreshHeader();
    }catch(e){ alert(e.message || 'Start failed'); }
  }
  async function doStop(){
    try{
      await api('POST', '/api/stop', {});
      await refreshHeader();
    }catch(e){ alert(e.message || 'Stop failed'); }
  }
  async function doRestart(){
    try{
      await api('POST', '/api/restart', {});
      await refreshHeader();
    }catch(e){ alert(e.message || 'Restart failed'); }
  }

  startBtn.addEventListener('click', doStart);
  stopBtn.addEventListener('click', doStop);
  restartBtn.addEventListener('click', doRestart);

  // Initial paint and polling
  refreshHeader();
  setInterval(refreshHeader, 2000);
})();

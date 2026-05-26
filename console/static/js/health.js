'use strict';

function statusDot(status) {
  const color = status === 'green' ? 'green' : status === 'amber' ? 'amber' : 'red';
  return `<span class="status-dot ${color}"></span>`;
}

function fmtSeconds(sec) {
  if (sec == null) return '—';
  if (sec < 60) return `${sec}s ago`;
  return `${Math.round(sec / 60)}min ago`;
}

async function loadHealth() {
  let data;
  try {
    const r = await fetch('/api/health/');
    data = await r.json();
  } catch (e) {
    console.error('Health fetch failed', e);
    return;
  }

  // Token tile
  const token = data.token || {};
  const tokenDot = document.getElementById('token-dot');
  tokenDot.className = `status-dot ${token.valid ? 'green' : 'red'}`;
  document.getElementById('token-valid').textContent = token.valid ? 'Valid' : 'Invalid / Unconfigured';
  document.getElementById('token-expiry').textContent = token.valid
    ? `Expires in ${token.expires_in_minutes}min`
    : data.ethos_configured ? 'Token not yet acquired' : 'No Ethos environment configured';

  // Queue tile
  document.getElementById('queue-depth').textContent = data.queue_depth ?? '—';
  const qs = data.queue_status || 'gray';
  document.getElementById('queue-status-text').innerHTML = `${statusDot(qs)} ${
    qs === 'green' ? 'Normal' : qs === 'amber' ? 'Moderate' : data.queue_error || 'High / Error'
  }`;

  // Latency tile
  const lat = data.latency || {};
  document.getElementById('msg-rate').textContent = lat.p50 != null ? `${lat.p50}ms` : '—';
  document.getElementById('msg-rate-sub').textContent = lat.sample_count
    ? `${lat.sample_count} samples`
    : 'No data yet';
  document.getElementById('lat-p50').textContent = lat.p50 != null ? `${lat.p50}ms` : '—';
  document.getElementById('lat-p95').textContent = lat.p95 != null ? `${lat.p95}ms` : '—';
  document.getElementById('lat-p99').textContent = lat.p99 != null ? `${lat.p99}ms` : '—';
  document.getElementById('lat-max').textContent = lat.max != null ? `${lat.max}ms` : '—';

  // Error tile
  const errCount = data.error_count_1h ?? 0;
  document.getElementById('error-count').textContent = errCount;
  document.getElementById('error-sub').innerHTML = statusDot(data.error_status || 'green') + (
    errCount === 0 ? 'No errors' : `${errCount} error${errCount !== 1 ? 's' : ''}`
  );

  // Resource health table
  const rh = data.resource_health || [];
  const tbody = document.getElementById('resource-health-tbody');
  if (!rh.length) {
    tbody.innerHTML = '<tr><td colspan="4" class="text-muted text-center py-3">No resource data yet</td></tr>';
  } else {
    tbody.innerHTML = rh.map(r => `<tr>
      <td class="font-monospace small">${r.resource}</td>
      <td class="text-end">${r.hourly_rate}</td>
      <td class="text-muted">${fmtSeconds(r.last_seen_seconds_ago)}</td>
      <td>${statusDot(r.status)} ${r.status === 'green' ? 'Normal' : '⚠ Silent'}</td>
    </tr>`).join('');
  }

  // Recent errors
  const errors = data.recent_errors || [];
  const errList = document.getElementById('error-list');
  if (!errors.length) {
    errList.innerHTML = '<div class="text-muted small">No errors recorded.</div>';
  } else {
    errList.innerHTML = errors.map(e => `
      <div class="d-flex justify-content-between small border-bottom py-1">
        <span class="text-muted">${e.timestamp}</span>
        <span class="font-monospace">${e.endpoint}</span>
        <span class="badge bg-danger">${e.status || 'ERR'}</span>
      </div>`).join('');
  }
}

async function refreshConsoleCaches() {
  const btn = document.querySelector('[onclick="refreshConsoleCaches()"]');
  const status = document.getElementById('cache-refresh-status');
  btn.disabled = true;
  status.className = 'small text-muted ms-2';
  status.textContent = 'Refreshing…';
  try {
    const r = await fetch('/api/health/caches/refresh', { method: 'POST' });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
    status.className = 'small text-success ms-2';
    status.textContent = `Cleared: ${(data.cleared || []).join(', ')}`;
  } catch (e) {
    status.className = 'small text-danger ms-2';
    status.textContent = `Failed: ${e.message}`;
  } finally {
    btn.disabled = false;
    setTimeout(() => { status.textContent = ''; }, 6000);
  }
}

loadHealth();
setInterval(loadHealth, 10000);

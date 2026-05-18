'use strict';

let totalEvents = 0;
let paused = false;
let evtSource = null;
let resourceStats = {};

function connectStream() {
  if (evtSource) evtSource.close();
  evtSource = new EventSource('/api/bus/stream');

  evtSource.onmessage = function (e) {
    let data;
    try { data = JSON.parse(e.data); } catch { return; }

    if (data.type === 'meta') {
      updateMetaTile(data);
      return;
    }
    if (data.type === 'error') {
      appendFeedRow(data, 'feed-error');
      return;
    }
    if (data.type === 'event') {
      totalEvents++;
      appendFeedRow(data, opClass(data.operation));
      updateResourceStats(data);
    }
  };

  evtSource.onerror = function () {
    appendRawRow('⚠ Stream disconnected — reconnecting...', 'feed-error');
    setTimeout(connectStream, 3000);
  };
}

function opClass(op) {
  switch ((op || '').toLowerCase()) {
    case 'created': return 'feed-created';
    case 'deleted': return 'feed-deleted';
    default:        return 'feed-updated';
  }
}

function appendFeedRow(data, cssClass) {
  const feed = document.getElementById('event-feed');
  const threshold = parseInt(document.getElementById('silence-threshold').value) || 30;
  const silentFlag = data.silent ? ` ⚠ No events for ${data.silent_minutes}min` : '';

  const ts = span('feed-ts', data.timestamp || '');
  const res = span('feed-resource', (data.resource || '').padEnd(36));
  const op = span('feed-op', (data.operation || '').padEnd(10));
  const guid = span('feed-guid', data.guid ? data.guid.substring(0, 36) : '');

  const row = document.createElement('div');
  row.className = `feed-row ${cssClass}`;
  row.appendChild(ts);
  row.appendChild(res);
  row.appendChild(op);
  row.appendChild(guid);
  if (silentFlag) row.appendChild(span('text-warning', silentFlag));

  feed.insertBefore(row, feed.firstChild);

  // cap at 300 DOM rows
  while (feed.children.length > 300) feed.removeChild(feed.lastChild);

  document.getElementById('tile-total').textContent = totalEvents;
}

function appendRawRow(text, cssClass) {
  const feed = document.getElementById('event-feed');
  const row = document.createElement('div');
  row.className = `feed-row ${cssClass}`;
  row.textContent = text;
  feed.insertBefore(row, feed.firstChild);
}

function span(cls, text) {
  const s = document.createElement('span');
  s.className = cls;
  s.textContent = text;
  return s;
}

function updateMetaTile(meta) {
  const depth = meta.queue_depth ?? '—';
  document.getElementById('tile-depth').textContent = depth;
  document.getElementById('tile-depth-status').textContent =
    depth >= 500 ? '🔴 High' : depth >= 100 ? '🟡 Moderate' : depth === '—' ? '' : '🟢 Normal';

  const pollAgo = meta.last_poll != null ? `Polled ${meta.last_poll}s ago` : 'Waiting...';
  document.getElementById('tile-last-poll').textContent = pollAgo;
}

function updateResourceStats(event) {
  const resource = event.resource || 'unknown';
  if (!resourceStats[resource]) {
    resourceStats[resource] = { count: 0, lastSeen: null, firstSeen: Date.now() };
  }
  resourceStats[resource].count++;
  resourceStats[resource].lastSeen = Date.now();
  renderResourceTable();
}

function renderResourceTable() {
  const tbody = document.getElementById('resource-tbody');
  const threshold = (parseInt(document.getElementById('silence-threshold').value) || 30) * 60 * 1000;
  const now = Date.now();
  const entries = Object.entries(resourceStats).sort((a, b) => b[1].count - a[1].count);

  let active = 0, silent = 0;
  const rows = entries.map(([resource, stats]) => {
    const elapsed = stats.lastSeen ? now - stats.lastSeen : null;
    const elapsedSec = elapsed != null ? Math.round(elapsed / 1000) : null;
    const isSilent = elapsed != null && elapsed > threshold;
    const elapsedDisplay = elapsedSec != null
      ? (elapsedSec < 60 ? `${elapsedSec}s ago` : `${Math.round(elapsedSec/60)}min ago`)
      : '—';

    const durationHours = stats.firstSeen ? (now - stats.firstSeen) / 3600000 : 0.001;
    const rate = Math.round(stats.count / Math.max(durationHours, 1/60));

    if (isSilent) silent++; else active++;

    const statusBadge = isSilent
      ? `<span class="badge badge-silent">⚠ Silent &gt;${threshold/60000}min</span>`
      : `<span class="badge badge-active">✓ Active</span>`;

    return `<tr>
      <td class="font-monospace small">${resource}</td>
      <td class="text-end">${rate}</td>
      <td class="text-muted">${elapsedDisplay}</td>
      <td>${statusBadge}</td>
    </tr>`;
  }).join('');

  tbody.innerHTML = rows || '<tr><td colspan="4" class="text-muted text-center py-3">No events yet</td></tr>';

  document.getElementById('tile-resources').textContent = active;
  document.getElementById('tile-silent').textContent = silent > 0
    ? `${silent} silent >threshold`
    : '0 silent';

  const total = entries.reduce((s, [, v]) => s + v.count, 0);
  const durationHours = entries.length > 0
    ? (Date.now() - Math.min(...entries.map(([,v]) => v.firstSeen))) / 3600000
    : 0.001;
  document.getElementById('tile-rate').textContent = Math.round(total / Math.max(durationHours, 1/60));
}

// Controls
document.getElementById('btn-pause').addEventListener('click', function () {
  paused = !paused;
  const label = paused ? '<i class="bi bi-play-fill"></i> Resume' : '<i class="bi bi-pause-fill"></i> Pause';
  this.innerHTML = label;
  document.getElementById('tile-paused-status').textContent = paused ? 'Paused' : 'Streaming';
  fetch(`/api/bus/${paused ? 'pause' : 'resume'}`, { method: 'POST' });
});

document.getElementById('btn-clear').addEventListener('click', function () {
  document.getElementById('event-feed').innerHTML = '';
  totalEvents = 0;
  resourceStats = {};
  document.getElementById('tile-total').textContent = '0';
  document.getElementById('tile-resources').textContent = '—';
  document.getElementById('tile-silent').textContent = '— silent';
  document.getElementById('resource-tbody').innerHTML =
    '<tr><td colspan="4" class="text-muted text-center py-3">No events yet</td></tr>';
  fetch('/api/bus/clear', { method: 'POST' });
});

connectStream();

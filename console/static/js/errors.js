'use strict';

let currentPage = 1;
let totalPages = 1;
const PAGE_SIZE = 50;

// ── Tiles ─────────────────────────────────────────────────────────────────────

async function loadTiles() {
  try {
    const [allR, todayR] = await Promise.allSettled([
      fetch('/api/errors/?limit=1&offset=0').then(r => r.json()),
      fetch('/api/errors/?limit=1&offset=0&from_ts=' + todayIso()).then(r => r.json()),
    ]);
    if (allR.status === 'fulfilled') {
      document.getElementById('err-total').textContent = allR.value.total ?? '—';
    }
    if (todayR.status === 'fulfilled') {
      document.getElementById('err-today').textContent = todayR.value.total ?? '—';
      document.getElementById('err-today-label').textContent = new Date().toLocaleDateString();
    }

    const rateR = await fetch('/api/errors/?limit=1&offset=0&http_status=429');
    const rateData = await rateR.json();
    document.getElementById('err-429').textContent = rateData.total ?? '—';
  } catch (e) {
    console.error('Tile load error', e);
  }
}

function todayIso() {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d.toISOString();
}

// ── Spikes chart ──────────────────────────────────────────────────────────────

async function loadSpikes() {
  const container = document.getElementById('spikes-chart');
  try {
    const r = await fetch('/api/errors/spikes');
    const data = await r.json();
    if (!data.length) {
      container.innerHTML = '<div class="text-muted small text-center py-3">No error data</div>';
      return;
    }

    const max = Math.max(...data.map(d => d.count), 1);
    let peakCount = 0;
    let peakHour = '';
    data.forEach(d => { if (d.count > peakCount) { peakCount = d.count; peakHour = d.hour; } });

    document.getElementById('err-spikes').textContent = peakCount;
    document.getElementById('err-spike-hour').textContent = peakHour ? peakHour.replace('T', ' ').substring(0, 13) + 'h' : '';

    container.innerHTML = data.map(d => {
      const pct = Math.round((d.count / max) * 100);
      const label = d.hour ? d.hour.substring(11, 13) + ':00' : '';
      const date  = d.hour ? d.hour.substring(0, 10) : '';
      return `<div class="d-flex align-items-center gap-2 mb-1" title="${d.hour} — ${d.count} errors">
        <div class="text-muted" style="font-size:.68rem;width:38px;text-align:right">${label}</div>
        <div style="flex:1;background:#e2e4e8;border-radius:3px;height:14px;">
          <div style="width:${pct}%;background:${pct > 80 ? '#dc3545' : pct > 40 ? '#ffc107' : '#6c757d'};height:100%;border-radius:3px;"></div>
        </div>
        <div style="font-size:.72rem;width:28px">${d.count}</div>
      </div>`;
    }).join('');
  } catch (e) {
    container.innerHTML = `<div class="text-danger small">Error: ${e.message}</div>`;
  }
}

// ── Error table ───────────────────────────────────────────────────────────────

async function loadErrors(resetPage) {
  if (resetPage) currentPage = 1;

  const source   = document.getElementById('filter-source').value;
  const status   = document.getElementById('filter-status').value;
  const resource = document.getElementById('filter-resource').value.trim();

  const params = new URLSearchParams({
    limit: PAGE_SIZE,
    offset: (currentPage - 1) * PAGE_SIZE,
  });
  if (source)   params.set('source', source);
  if (status)   params.set('http_status', status);
  if (resource) params.set('resource_name', resource);

  // Update CSV export link
  const exportParams = new URLSearchParams(params);
  exportParams.delete('limit');
  exportParams.delete('offset');
  document.getElementById('btn-export').href = '/api/errors/export?' + exportParams.toString();

  const tbody = document.getElementById('errors-tbody');
  tbody.innerHTML = '<tr><td colspan="6" class="text-center py-3 text-muted">Loading...</td></tr>';

  try {
    const r = await fetch('/api/errors/?' + params.toString());
    const data = await r.json();

    const total = data.total || 0;
    totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

    document.getElementById('errors-count').textContent =
      `${total} error${total !== 1 ? 's' : ''} — page ${currentPage} of ${totalPages}`;
    document.getElementById('page-info').textContent = `p ${currentPage}`;
    document.getElementById('btn-prev').disabled = currentPage <= 1;
    document.getElementById('btn-next').disabled = currentPage >= totalPages;

    const items = data.items || [];
    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-center py-3 text-muted">No errors match filters</td></tr>';
      return;
    }

    tbody.innerHTML = items.map(e => {
      const ts = e.timestamp ? new Date(e.timestamp).toLocaleString() : '—';
      const statusBadge = e.http_status
        ? `<span class="badge ${e.http_status >= 500 ? 'badge-error' : e.http_status === 429 ? 'badge-silent' : 'badge-unknown'}"
               style="font-size:.65rem">${e.http_status}</span>`
        : '—';
      const msg = (e.error_message || '').substring(0, 80) + (e.error_message?.length > 80 ? '…' : '');
      return `<tr>
        <td class="text-muted small" style="white-space:nowrap">${ts}</td>
        <td class="small font-monospace">${e.source || '—'}</td>
        <td class="small font-monospace" style="max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
            title="${e.endpoint || ''}">${e.endpoint || '—'}</td>
        <td>${statusBadge}</td>
        <td class="small font-monospace">${e.resource_name || '—'}</td>
        <td class="small d-none d-md-table-cell text-muted" title="${e.error_message || ''}">${msg || '—'}</td>
      </tr>`;
    }).join('');
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-danger small text-center py-3">${err.message}</td></tr>`;
  }
}

function prevPage() {
  if (currentPage > 1) { currentPage--; loadErrors(false); }
}

function nextPage() {
  if (currentPage < totalPages) { currentPage++; loadErrors(false); }
}

// ── Flush ─────────────────────────────────────────────────────────────────────

async function flushMemory() {
  const btn = document.querySelector('[onclick="flushMemory()"]');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Flushing...';
  try {
    await fetch('/api/errors/flush', { method: 'POST' });
    await loadErrors(true);
    await loadTiles();
  } catch (e) {
    alert('Flush failed: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-download me-1"></i>Flush in-memory';
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────
loadTiles();
loadErrors(true);
loadSpikes();

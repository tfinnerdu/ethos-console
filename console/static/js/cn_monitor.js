/* Change Notifications — cn_monitor.js */

// ── Section switcher ──────────────────────────────────────────────────────────

function cnSection(name) {
  document.getElementById('cn-section-monitor').style.display = name === 'monitor' ? '' : 'none';
  document.getElementById('cn-section-push').style.display    = name === 'push'    ? '' : 'none';
  document.getElementById('btn-section-monitor').classList.toggle('active', name === 'monitor');
  document.getElementById('btn-section-push').classList.toggle('active',    name === 'push');
}

// ── Bootstrap ────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  const monitorSection = document.getElementById('cn-section-monitor');
  if (monitorSection) {
    // Only wire up Monitor listeners when CNM tiles actually exist
    if (document.getElementById('tile-total')) {
      loadHealth();
      loadNotifications();
      loadDiagnostics();

      document.querySelector('[href="#tab-audit"]').addEventListener('shown.bs.tab', () => {
        if (auditTotalCount === 0) loadAuditLog(1);
      });
    }
  }
});

// ── Monitor state ─────────────────────────────────────────────────────────────

let allNotifications = [];
let currentCnId = null;
let auditCurrentPage = 1;
let auditTotalCount = 0;
const AUDIT_PAGE_SIZE = 50;

// ── Health ────────────────────────────────────────────────────────────────────

async function loadHealth() {
  try {
    const r = await fetch('/api/cn/health');
    const dot = document.getElementById('cnm-dot');
    const txt = document.getElementById('cnm-status-text');
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const d = await r.json();
    dot.className = 'status-dot green';
    txt.textContent = `v${d.version || '?'} · up ${fmtUptime(d.uptime_seconds)}`;
  } catch (e) {
    document.getElementById('cnm-dot').className = 'status-dot red';
    document.getElementById('cnm-status-text').textContent = 'Unreachable - ' + e.message;
  }
}

function fmtUptime(secs) {
  if (!secs) return '0s';
  const h = Math.floor(secs / 3600), m = Math.floor((secs % 3600) / 60), s = secs % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

// ── Notifications ─────────────────────────────────────────────────────────────

async function loadNotifications() {
  try {
    const r = await fetch('/api/cn/notifications');
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    allNotifications = data.items || [];

    const enabled  = allNotifications.filter(n => n.status === 'Enabled').length;
    const disabled = allNotifications.filter(n => n.status === 'Disabled').length;
    document.getElementById('tile-total').textContent   = allNotifications.length;
    document.getElementById('tile-enabled').textContent  = enabled;
    document.getElementById('tile-disabled').textContent = disabled;

    renderNotifications(allNotifications);
  } catch (e) {
    document.getElementById('cn-tbody').innerHTML =
      `<tr><td colspan="4" class="text-danger small">${e.message}</td></tr>`;
  }
}

function filterNotifications() {
  const q  = document.getElementById('cn-search').value.toLowerCase();
  const st = document.getElementById('cn-status-filter').value;
  renderNotifications(allNotifications.filter(n =>
    (!q  || n.resourceName.toLowerCase().includes(q) || (n.description || '').toLowerCase().includes(q)) &&
    (!st || n.status === st)
  ));
}

function renderNotifications(items) {
  const tbody = document.getElementById('cn-tbody');
  if (!items.length) {
    tbody.innerHTML = '<tr><td colspan="4" class="text-muted small text-center py-3">No results</td></tr>';
    return;
  }
  tbody.innerHTML = items.map(n => `
    <tr class="${currentCnId === n.id ? 'table-active' : ''}"
        onclick="selectNotification('${esc(n.id)}')" style="cursor:pointer">
      <td class="small font-monospace">${esc(n.resourceName)}</td>
      <td>${statusBadge(n.status)}</td>
      <td class="text-center">${n.hasParagraph ? '<i class="bi bi-file-text text-info"></i>' : ''}</td>
      <td class="text-muted small">${fmtDate(n.lastModified)}</td>
    </tr>`).join('');
}

async function selectNotification(id) {
  currentCnId = id;
  filterNotifications();

  const detail = document.getElementById('cn-detail');
  detail.innerHTML = '<div class="card-body text-muted small">Loading...</div>';

  try {
    const [detailR, histR] = await Promise.all([
      fetch(`/api/cn/notifications/${encodeURIComponent(id)}`),
      fetch(`/api/cn/notifications/${encodeURIComponent(id)}/history`),
    ]);

    const n = detailR.ok ? await detailR.json() : null;
    const history = histR.ok ? (await histR.json()).items || [] : [];

    if (!n) { detail.innerHTML = '<div class="card-body text-danger small">Not found</div>'; return; }

    const paraHtml = n.paragraphCode
      ? `<span class="badge bg-secondary font-monospace">${esc(n.paragraphCode)}</span>`
      : '<span class="text-muted">-</span>';
    const procHtml = n.processCode
      ? `<span class="badge bg-secondary font-monospace">${esc(n.processCode)}</span>`
      : '<span class="text-muted">-</span>';

    const params   = (n.parameters || []).map(p => `<li class="font-monospace">${esc(p)}</li>`).join('') || '<li class="text-muted">none</li>';
    const edps     = (n.edpsRules  || []).map(r => `<li class="font-monospace">${esc(r)}</li>`).join('') || '<li class="text-muted">none</li>';
    const histRows = history.slice(0, 10).map(h => `
      <tr>
        <td class="small">${fmtDate(h.timestamp)}</td>
        <td class="small">${esc(h.userDisplayName || h.userId || '-')}</td>
        <td><span class="badge ${h.outcome === 'Success' ? 'bg-success' : 'bg-danger'}">${esc(h.action)}</span></td>
      </tr>`).join('') || '<tr><td colspan="3" class="text-muted small">No history</td></tr>';

    detail.innerHTML = `
      <div class="card-header d-flex justify-content-between align-items-center py-2">
        <span class="fw-semibold small font-monospace">${esc(n.resourceName)}</span>
        ${statusBadge(n.status)}
      </div>
      <div class="card-body small" style="overflow-y:auto;max-height:calc(100vh - 360px)">
        <p class="text-muted mb-2">${esc(n.description)}</p>
        <div class="row g-2 mb-3">
          <div class="col-6"><div class="text-muted">Paragraph Code</div>${paraHtml}</div>
          <div class="col-6"><div class="text-muted">Process Code</div>${procHtml}</div>
        </div>
        <div class="mb-3">
          <div class="text-muted mb-1">Parameters</div>
          <ul class="mb-0 ps-3 small">${params}</ul>
        </div>
        <div class="mb-3">
          <div class="text-muted mb-1">EDPS Rules</div>
          <ul class="mb-0 ps-3 small">${edps}</ul>
        </div>
        <div>
          <div class="text-muted mb-1">Recent History</div>
          <table class="table table-sm mb-0">
            <thead class="table-light"><tr><th>When</th><th>User</th><th>Action</th></tr></thead>
            <tbody>${histRows}</tbody>
          </table>
        </div>
      </div>`;
  } catch (e) {
    detail.innerHTML = `<div class="card-body text-danger small">${e.message}</div>`;
  }
}

// ── Diagnostics ───────────────────────────────────────────────────────────────

async function loadDiagnostics() {
  try {
    const r = await fetch('/api/cn/diagnostics');
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const d = await r.json();

    document.getElementById('tile-subscribed').textContent = d.totalSubscribed ?? '-';
    document.getElementById('tile-published').textContent  = d.totalPublished  ?? '-';

    const snp     = d.subscribedNotPublished || [];
    const pns     = d.publishedNotSubscribed || [];
    const aligned = d.aligned || [];
    document.getElementById('tile-gaps').textContent = snp.length + pns.length;

    const fill = (listId, countId, items) => {
      document.getElementById(countId).textContent = items.length;
      document.getElementById(listId).innerHTML = items.length
        ? items.map(r => `<li>${esc(r)}</li>`).join('')
        : '<li class="text-muted">None</li>';
    };
    fill('diag-aligned-list', 'diag-aligned-count', aligned);
    fill('diag-snp-list',     'diag-snp-count',     snp);
    fill('diag-pns-list',     'diag-pns-count',     pns);

    document.getElementById('diag-loading').style.display = 'none';
    document.getElementById('diag-content').style.removeProperty('display');
  } catch (e) {
    const el = document.getElementById('diag-loading');
    el.textContent = 'Failed to load diagnostics: ' + e.message;
    el.className = 'text-danger small';
  }
}

// ── Audit log ─────────────────────────────────────────────────────────────────

async function loadAuditLog(page) {
  auditCurrentPage = page;
  const target = document.getElementById('audit-target').value.trim();
  const params = new URLSearchParams({ page, pageSize: AUDIT_PAGE_SIZE });
  if (target) params.set('targetIdentifier', target);

  try {
    const r = await fetch('/api/cn/audit-log?' + params);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const d = await r.json();
    auditTotalCount = d.totalCount || 0;

    const tbody = document.getElementById('audit-tbody');
    const items = d.items || [];
    tbody.innerHTML = items.length
      ? items.map(e => `
        <tr>
          <td class="small">${fmtDate(e.timestamp)}</td>
          <td class="small">${esc(e.userDisplayName || e.userId || '-')}</td>
          <td><span class="badge bg-secondary">${esc(e.action)}</span></td>
          <td class="small font-monospace">${esc(e.targetIdentifier || e.targetType || '-')}</td>
          <td><span class="badge ${e.outcome === 'Success' ? 'bg-success' : 'bg-danger'}">${esc(e.outcome)}</span></td>
        </tr>`).join('')
      : '<tr><td colspan="5" class="text-muted small text-center py-3">No entries</td></tr>';

    const totalPages = Math.ceil(auditTotalCount / AUDIT_PAGE_SIZE) || 1;
    document.getElementById('audit-page-label').textContent = `Page ${page} of ${totalPages}`;
    document.getElementById('audit-prev').disabled = page <= 1;
    document.getElementById('audit-next').disabled = page >= totalPages;
  } catch (e) {
    document.getElementById('audit-tbody').innerHTML =
      `<tr><td colspan="5" class="text-danger small">${e.message}</td></tr>`;
  }
}

function auditPage(delta) { loadAuditLog(auditCurrentPage + delta); }

// ── Push ──────────────────────────────────────────────────────────────────────

let pushRunning = false;
const pushResults = new Map();

function updatePushGuidCount() {
  const n = parsePushGuids().length;
  document.getElementById('push-guid-count').textContent = `(${n} entered)`;
}

function parsePushGuids() {
  const el = document.getElementById('push-guids');
  if (!el) return [];
  return el.value.split('\n').map(s => s.trim()).filter(s => s.length > 0);
}

async function runPush() {
  if (pushRunning) return;

  const resourceName = (document.getElementById('push-resource').value || '').trim();
  const operation    = document.getElementById('push-operation').value;
  const guids        = parsePushGuids();

  if (!resourceName) { alert('Enter a resource name.'); return; }
  if (!guids.length) { alert('Enter at least one GUID.'); return; }

  pushRunning = true;
  const btn = document.getElementById('push-run-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Running...';

  const progress = document.getElementById('push-progress');
  if (progress) progress.style.removeProperty('display');

  clearPushResults(false);
  for (const guid of guids) upsertPushResult(guid, { status: 'pending' });

  try {
    const r = await fetch('/api/cn/push', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ resource_name: resourceName, operation, guids }),
    });
    const data = await r.json();
    if (!r.ok) {
      for (const guid of guids) upsertPushResult(guid, { status: 'error', error: data.error || `HTTP ${r.status}` });
    } else {
      for (const result of (data.results || [])) upsertPushResult(result.guid, result);
    }
  } catch (e) {
    for (const guid of guids) upsertPushResult(guid, { status: 'error', error: e.message });
  }

  if (progress) progress.style.display = 'none';
  pushRunning = false;
  btn.disabled = false;
  btn.innerHTML = '<i class="bi bi-send me-1"></i>Publish Change Notifications';
}

function upsertPushResult(guid, data) {
  pushResults.set(guid, data);
  updatePushStats();

  const list  = document.getElementById('push-results-list');
  const empty = document.getElementById('push-empty');
  if (empty) empty.style.display = 'none';

  const borderCls = data.status === 'success' ? 'border-success'
                  : data.status === 'error'   ? 'border-danger'
                  :                             'border-warning';
  const badgeCls  = data.status === 'success' ? 'bg-success'
                  : data.status === 'error'   ? 'bg-danger'
                  :                             'bg-warning text-dark';

  const safeId = guid.replace(/[^a-z0-9]/gi, '');

  let card = document.getElementById(`push-card-${safeId}`);
  if (!card) {
    card = document.createElement('div');
    card.id = `push-card-${safeId}`;
    card.innerHTML = `
      <div class="card mb-2 border-start border-3 ${borderCls}" id="push-card-inner-${safeId}">
        <div class="card-header d-flex align-items-center gap-2 py-2 small"
             style="cursor:pointer"
             data-bs-toggle="collapse" data-bs-target="#push-body-${safeId}">
          <span class="font-monospace flex-grow-1 text-truncate">${esc(guid)}</span>
          <span class="badge ${badgeCls}" id="push-badge-${safeId}">${data.status}</span>
          <span class="text-muted font-monospace" id="push-ver-${safeId}" style="font-size:.7rem"></span>
          <i class="bi bi-chevron-down ms-1 text-muted"></i>
        </div>
        <div class="collapse" id="push-body-${safeId}">
          <div class="card-body small font-monospace py-2" id="push-detail-${safeId}"></div>
        </div>
      </div>`;
    list.appendChild(card);
  }

  const inner = document.getElementById(`push-card-inner-${safeId}`);
  if (inner) inner.className = `card mb-2 border-start border-3 ${borderCls}`;

  const badge = document.getElementById(`push-badge-${safeId}`);
  if (badge) { badge.className = `badge ${badgeCls}`; badge.textContent = data.status; }

  const ver = document.getElementById(`push-ver-${safeId}`);
  if (ver && data.version) ver.textContent = data.version;

  const detail = document.getElementById(`push-detail-${safeId}`);
  if (detail) {
    if (data.status === 'pending') {
      detail.innerHTML = '<span class="text-muted">Waiting...</span>';
    } else if (data.status === 'error') {
      detail.innerHTML = `<span class="text-danger">${esc(data.error || 'Unknown error')}</span>`;
    } else {
      detail.innerHTML = `<span class="text-success">Published OK</span>${data.version ? ` &nbsp;<span class="text-muted">version: ${esc(data.version)}</span>` : ''}`;
    }
  }
}

function updatePushStats() {
  let pending = 0, success = 0, error = 0;
  for (const r of pushResults.values()) {
    if (r.status === 'pending')      pending++;
    else if (r.status === 'success') success++;
    else                             error++;
  }
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
  set('push-stat-pending', pending);
  set('push-stat-success', success);
  set('push-stat-error',   error);
}

function clearPushResults(resetMap = true) {
  if (resetMap) pushResults.clear();
  updatePushStats();
  const list = document.getElementById('push-results-list');
  if (!list) return;
  list.innerHTML = `
    <div id="push-empty" class="text-muted small text-center py-5">
      <i class="bi bi-inbox fs-3 d-block mb-2 opacity-25"></i>
      Configure settings and click Publish to begin.
    </div>`;
}

// ── Shared helpers ────────────────────────────────────────────────────────────

function statusBadge(status) {
  const cls = status === 'Enabled'  ? 'bg-success'
            : status === 'Disabled' ? 'bg-warning text-dark'
            :                         'bg-secondary';
  return `<span class="badge ${cls}">${status || 'Unknown'}</span>`;
}

function fmtDate(iso) {
  if (!iso) return '-';
  const d = new Date(iso);
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function esc(s) {
  if (s == null) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

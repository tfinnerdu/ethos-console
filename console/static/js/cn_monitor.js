/* Change Notification Monitor — cn_monitor.js */

let allNotifications = [];
let currentCnId = null;
let auditCurrentPage = 1;
let auditTotalCount = 0;
const AUDIT_PAGE_SIZE = 50;

// ── Bootstrap ────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  loadHealth();
  loadNotifications();
  loadDiagnostics();  // preload so the tab is ready

  document.querySelector('[href="#tab-audit"]').addEventListener('shown.bs.tab', () => {
    if (auditTotalCount === 0) loadAuditLog(1);
  });
});

// ── Health ────────────────────────────────────────────────────────────────────

async function loadHealth() {
  try {
    const r = await fetch('/api/cn/health');
    const dot = document.getElementById('cnm-dot');
    const txt = document.getElementById('cnm-status-text');
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const d = await r.json();
    dot.className = 'status-dot dot-green';
    txt.textContent = `v${d.version || '?'} · up ${fmtUptime(d.uptime_seconds)}`;
  } catch (e) {
    document.getElementById('cnm-dot').className = 'status-dot dot-red';
    document.getElementById('cnm-status-text').textContent = 'Unreachable — ' + e.message;
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

    const enabled = allNotifications.filter(n => n.status === 'Enabled').length;
    const disabled = allNotifications.filter(n => n.status === 'Disabled').length;
    document.getElementById('tile-total').textContent = allNotifications.length;
    document.getElementById('tile-enabled').textContent = enabled;
    document.getElementById('tile-disabled').textContent = disabled;

    renderNotifications(allNotifications);
  } catch (e) {
    document.getElementById('cn-tbody').innerHTML =
      `<tr><td colspan="4" class="text-danger small">${e.message}</td></tr>`;
  }
}

function filterNotifications() {
  const q = document.getElementById('cn-search').value.toLowerCase();
  const st = document.getElementById('cn-status-filter').value;
  const filtered = allNotifications.filter(n =>
    (!q || n.resourceName.toLowerCase().includes(q) || n.description.toLowerCase().includes(q)) &&
    (!st || n.status === st)
  );
  renderNotifications(filtered);
}

function renderNotifications(items) {
  const tbody = document.getElementById('cn-tbody');
  if (!items.length) {
    tbody.innerHTML = '<tr><td colspan="4" class="text-muted small text-center py-3">No results</td></tr>';
    return;
  }
  tbody.innerHTML = items.map(n => `
    <tr class="cn-row${currentCnId === n.id ? ' table-active' : ''}"
        onclick="selectNotification('${esc(n.id)}')" style="cursor:pointer">
      <td class="small font-monospace">${esc(n.resourceName)}</td>
      <td>${statusBadge(n.status)}</td>
      <td class="text-center">${n.hasParagraph ? '<i class="bi bi-file-text text-info"></i>' : ''}</td>
      <td class="text-muted small">${fmtDate(n.lastModified)}</td>
    </tr>`).join('');
}

async function selectNotification(id) {
  currentCnId = id;
  // Re-render list to highlight selection
  filterNotifications();

  const detail = document.getElementById('cn-detail');
  detail.innerHTML = '<div class="card-body text-muted small">Loading…</div>';

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
      : '<span class="text-muted">—</span>';
    const procHtml = n.processCode
      ? `<span class="badge bg-secondary font-monospace">${esc(n.processCode)}</span>`
      : '<span class="text-muted">—</span>';

    const params = (n.parameters || []).map(p => `<li class="font-monospace">${esc(p)}</li>`).join('') || '<li class="text-muted">none</li>';
    const edps = (n.edpsRules || []).map(r => `<li class="font-monospace">${esc(r)}</li>`).join('') || '<li class="text-muted">none</li>';

    const histRows = history.slice(0, 10).map(h => `
      <tr>
        <td class="small">${fmtDate(h.timestamp)}</td>
        <td class="small">${esc(h.userDisplayName || h.userId || '—')}</td>
        <td><span class="badge ${h.outcome === 'Success' ? 'bg-success' : 'bg-danger'}">${esc(h.action)}</span></td>
      </tr>`).join('') || '<tr><td colspan="3" class="text-muted small">No history</td></tr>';

    detail.innerHTML = `
      <div class="card-header d-flex justify-content-between align-items-center py-2">
        <span class="fw-semibold small font-monospace">${esc(n.resourceName)}</span>
        ${statusBadge(n.status)}
      </div>
      <div class="card-body small" style="overflow-y:auto;max-height:calc(100vh - 340px)">
        <p class="text-muted mb-2">${esc(n.description)}</p>
        <div class="row g-2 mb-3">
          <div class="col-6">
            <div class="text-muted">Paragraph Code</div>${paraHtml}
          </div>
          <div class="col-6">
            <div class="text-muted">Process Code</div>${procHtml}
          </div>
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

    document.getElementById('tile-subscribed').textContent = d.totalSubscribed ?? '—';
    document.getElementById('tile-published').textContent = d.totalPublished ?? '—';

    const snp = d.subscribedNotPublished || [];
    const pns = d.publishedNotSubscribed || [];
    const aligned = d.aligned || [];
    document.getElementById('tile-gaps').textContent = snp.length + pns.length;

    const fill = (listId, countId, items) => {
      document.getElementById(countId).textContent = items.length;
      document.getElementById(listId).innerHTML =
        items.length
          ? items.map(r => `<li>${esc(r)}</li>`).join('')
          : '<li class="text-muted">None</li>';
    };

    fill('diag-aligned-list', 'diag-aligned-count', aligned);
    fill('diag-snp-list',     'diag-snp-count',     snp);
    fill('diag-pns-list',     'diag-pns-count',     pns);

    document.getElementById('diag-loading').style.display = 'none';
    document.getElementById('diag-content').style.removeProperty('display');
  } catch (e) {
    document.getElementById('diag-loading').textContent = 'Failed to load diagnostics: ' + e.message;
    document.getElementById('diag-loading').className = 'text-danger small';
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
    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="text-muted small text-center py-3">No entries</td></tr>';
    } else {
      tbody.innerHTML = items.map(e => `
        <tr>
          <td class="small">${fmtDate(e.timestamp)}</td>
          <td class="small">${esc(e.userDisplayName || e.userId || '—')}</td>
          <td><span class="badge bg-secondary">${esc(e.action)}</span></td>
          <td class="small font-monospace">${esc(e.targetIdentifier || e.targetType || '—')}</td>
          <td><span class="badge ${e.outcome === 'Success' ? 'bg-success' : 'bg-danger'}">${esc(e.outcome)}</span></td>
        </tr>`).join('');
    }

    const totalPages = Math.ceil(auditTotalCount / AUDIT_PAGE_SIZE) || 1;
    document.getElementById('audit-page-label').textContent = `Page ${page} of ${totalPages}`;
    document.getElementById('audit-prev').disabled = page <= 1;
    document.getElementById('audit-next').disabled = page >= totalPages;
  } catch (e) {
    document.getElementById('audit-tbody').innerHTML =
      `<tr><td colspan="5" class="text-danger small">${e.message}</td></tr>`;
  }
}

function auditPage(delta) {
  loadAuditLog(auditCurrentPage + delta);
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function statusBadge(status) {
  const cls = status === 'Enabled' ? 'bg-success'
            : status === 'Disabled' ? 'bg-warning text-dark'
            : 'bg-secondary';
  return `<span class="badge ${cls}">${status || 'Unknown'}</span>`;
}

function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function esc(s) {
  if (s == null) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

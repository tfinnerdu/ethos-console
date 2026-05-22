'use strict';

let allEventConfigs = [];

function escapeHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ── Connection test ───────────────────────────────────────────────────────────

async function testConnection() {
  const dot = document.getElementById('capi-status-dot');
  const text = document.getElementById('capi-status-text');
  dot.style.background = '#ffc107';
  text.textContent = 'Connecting…';
  try {
    const r = await fetch('/api/colleague/about');
    const data = await r.json();
    if (data.error) {
      dot.style.background = '#dc3545';
      text.textContent = data.error;
      return;
    }
    dot.style.background = '#198754';
    const version = data.productVersion || data.version || data.Version
      || data.releaseVersion || data.ReleaseVersion || '';
    text.textContent = version ? `Connected — v${version}` : 'Connected';
    showDetail('API Info', data);
  } catch (e) {
    dot.style.background = '#dc3545';
    text.textContent = `Error: ${e.message}`;
  }
}

// ── Event Configurations ──────────────────────────────────────────────────────

async function loadEventConfigs() {
  const list = document.getElementById('evcfg-list');
  list.innerHTML = '<div class="text-center py-2"><span class="spinner-border spinner-border-sm"></span></div>';
  try {
    const r = await fetch('/api/colleague/event-configurations');
    const data = await r.json();
    if (data.error) {
      list.innerHTML = `<div class="text-danger small px-1">${escapeHtml(data.error)}<br><small class="text-muted">${escapeHtml(data.setup || '')}</small></div>`;
      return;
    }
    allEventConfigs = Array.isArray(data) ? data : [];
    renderEventConfigs(allEventConfigs);
  } catch (e) {
    list.innerHTML = `<div class="text-danger small px-1">Network error: ${e.message}</div>`;
  }
}

function renderEventConfigs(configs) {
  const list = document.getElementById('evcfg-list');
  if (!configs.length) {
    list.innerHTML = '<div class="text-muted small text-center py-2">No configurations found.</div>';
    return;
  }
  list.innerHTML = configs.map((cfg, i) => {
    const name = cfg.resourceName || cfg.ResourceName || cfg.name || `Config ${i}`;
    const enabled = cfg.enabled ?? cfg.Enabled;
    const badge = enabled === false
      ? '<span class="badge bg-secondary ms-1" style="font-size:.65rem">off</span>'
      : '<span class="badge bg-success ms-1" style="font-size:.65rem">on</span>';
    return `<div class="schema-resource-header d-flex justify-content-between align-items-center"
                 onclick="showEventConfig(${i})" style="cursor:pointer;font-size:.75rem">
      <span>${escapeHtml(name)}</span>${badge}
    </div>`;
  }).join('');
}

function filterEventConfigs() {
  const q = document.getElementById('evcfg-search').value.toLowerCase();
  if (!q) { renderEventConfigs(allEventConfigs); return; }
  renderEventConfigs(allEventConfigs.filter(c => {
    const n = (c.resourceName || c.ResourceName || c.name || '').toLowerCase();
    return n.includes(q);
  }));
}

function showEventConfig(idx) {
  const cfg = allEventConfigs[idx];
  if (!cfg) return;
  const name = cfg.resourceName || cfg.ResourceName || cfg.name || `Config ${idx}`;
  showDetail(name, cfg);
}

function showDetail(title, data) {
  const card = document.getElementById('capi-detail-card');
  document.getElementById('capi-detail-title').textContent = title;
  document.getElementById('capi-detail-content').innerHTML =
    `<pre class="small mb-0" style="max-height:260px;overflow:auto;font-size:.72rem">${escapeHtml(JSON.stringify(data, null, 2))}</pre>`;
  card.style.display = '';
}

// ── CTX Transaction Caller ────────────────────────────────────────────────────

function formatPayload() {
  const ta = document.getElementById('ctx-payload');
  try {
    ta.value = JSON.stringify(JSON.parse(ta.value), null, 2);
  } catch (_) {}
}

async function callTransaction() {
  const txId = document.getElementById('ctx-tx-id').value.trim().toUpperCase();
  const payloadText = document.getElementById('ctx-payload').value.trim();
  const btn = document.getElementById('btn-ctx-call');
  const meta = document.getElementById('ctx-meta');
  const result = document.getElementById('ctx-result');

  if (!txId) {
    result.innerHTML = '<div class="text-warning small">Enter a Transaction ID.</div>';
    return;
  }

  const confirmed = await confirmAction({
    title: 'Call CTX transaction',
    message: 'This runs ENVISION process "' + txId + '" against Colleague.\n\n'
      + 'Write processes (SAVE.*, UPDATE.*, DELETE.*) mutate Colleague data immediately, '
      + 'with no undo. Confirm the transaction ID is what you intend to run.',
    confirmLabel: 'Call transaction',
    danger: true,
    requireText: txId,
  });
  if (!confirmed) return;

  let payload = {};
  if (payloadText) {
    try { payload = JSON.parse(payloadText); }
    catch (e) {
      result.innerHTML = `<div class="text-danger small">Invalid JSON payload: ${escapeHtml(e.message)}</div>`;
      return;
    }
  }

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Calling…';
  meta.textContent = '';
  result.innerHTML = '';

  const t0 = Date.now();
  try {
    const r = await fetch('/api/colleague/transaction', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ transactionId: txId, payload }),
    });
    const data = await r.json();
    const elapsed = Date.now() - t0;
    meta.textContent = `${elapsed}ms`;

    if (data.error) {
      result.innerHTML = `<div class="text-danger small">${escapeHtml(data.error)}<br><small class="text-muted">${escapeHtml(data.setup || '')}</small></div>`;
      return;
    }

    const statusClass = r.ok ? 'success' : 'warning';
    result.innerHTML = `
      <div class="d-flex justify-content-between align-items-center mb-1">
        <span class="badge bg-${statusClass}">${r.status} ${r.statusText || 'OK'}</span>
        <button class="btn py-0 text-muted" style="font-size:.75rem"
                onclick="copyResult()" title="Copy JSON">
          <i class="bi bi-clipboard me-1"></i>Copy
        </button>
      </div>
      <pre id="ctx-result-json" class="small font-monospace mb-0"
           style="max-height:340px;overflow:auto;background:#f8f9fa;padding:.5rem;border-radius:4px;font-size:.73rem">${escapeHtml(JSON.stringify(data, null, 2))}</pre>`;
  } catch (e) {
    result.innerHTML = `<div class="text-danger small">Network error: ${escapeHtml(e.message)}</div>`;
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-send me-1"></i>Call';
  }
}

function copyResult() {
  const pre = document.getElementById('ctx-result-json');
  if (pre) navigator.clipboard.writeText(pre.textContent).catch(() => {});
}

function clearTransaction() {
  document.getElementById('ctx-tx-id').value = '';
  document.getElementById('ctx-payload').value = '';
  document.getElementById('ctx-result').innerHTML = '';
  document.getElementById('ctx-meta').textContent = '';
}

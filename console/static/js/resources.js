'use strict';

let allResources = [];
let cnSet = new Set();
let annotationMap = {};
let currentFilter = 'all';
let selectedResource = null;
let resourceError = null;

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s == null ? '' : String(s);
  return d.innerHTML;
}

async function loadResources() {
  document.getElementById('resource-status').textContent = 'Fetching from Ethos...';
  const [resR, cnR, annR] = await Promise.allSettled([
    fetch('/api/resources/').then(r => r.json()),
    fetch('/api/resources/cn-enabled').then(r => r.json()),
    fetch('/api/resources/annotations').then(r => r.json()),
  ]);

  if (resR.status === 'fulfilled') {
    allResources = resR.value.items || [];
    resourceError = resR.value.error || null;
  } else {
    allResources = [];
    resourceError = (resR.reason && resR.reason.message) || 'Failed to reach the console API';
  }
  if (cnR.status === 'fulfilled' && cnR.value.items) {
    cnSet = new Set((cnR.value.items || []).map(i => i.resourceName || i.name || i));
  }
  if (annR.status === 'fulfilled') {
    annotationMap = {};
    (annR.value?.items || []).forEach(a => { annotationMap[a.resource_name] = a; });
  }

  renderTable();
}

function renderTable() {
  const q = (document.getElementById('resource-search').value || '').toLowerCase();
  let rows = allResources.filter(r => {
    const name = resourceName(r).toLowerCase();
    if (q && !name.includes(q)) return false;
    if (currentFilter === 'cn') return cnSet.has(resourceName(r));
    if (currentFilter === 'gap') return annotationMap[resourceName(r)]?.trigger_conditions_gap;
    return true;
  });

  const total = allResources.length;
  const statusEl = document.getElementById('resource-status');
  if (!total && resourceError) {
    statusEl.className = 'small mb-2 text-danger';
    statusEl.textContent = `Could not load resources — ${resourceError}`;
  } else {
    statusEl.className = 'text-muted small mb-2';
    statusEl.textContent =
      total ? `Showing ${rows.length} of ${total} resources` : 'No resources — check ETHOS_API_KEY';
  }

  const tbody = document.getElementById('resource-list-tbody');
  if (!rows.length) {
    tbody.innerHTML = (!total && resourceError)
      ? `<tr><td colspan="4" class="text-danger text-center py-3">${esc(resourceError)}</td></tr>`
      : '<tr><td colspan="4" class="text-muted text-center py-3">No matches</td></tr>';
    return;
  }

  tbody.innerHTML = rows.map(r => {
    const name = resourceName(r);
    const ver = r.latestVersion || r.version || '—';
    const isCn = cnSet.has(name);
    const ann = annotationMap[name];
    const isGap = ann?.trigger_conditions_gap;
    const isSel = selectedResource === name;

    return `<tr class="resource-row${isSel ? ' selected' : ''}" onclick="selectResource('${name}', '${ver}', ${JSON.stringify((r.versions||[]).join(', ') || ver)})">
      <td class="font-monospace small">${name}</td>
      <td class="text-muted small">v${ver}</td>
      <td>${isCn ? '<span class="badge badge-active" style="font-size:.65rem">CN ✓</span>' : '<span class="badge badge-unknown" style="font-size:.65rem">—</span>'}</td>
      <td>${isGap ? '<i class="bi bi-exclamation-triangle-fill text-warning" title="TRIGGER_CONDITIONS gap"></i>' : ''}</td>
    </tr>`;
  }).join('');
}

function resourceName(r) {
  return r.name || r.resourceName || '';
}

function setFilter(f, btn) {
  currentFilter = f;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderTable();
}

function filterTable() { renderTable(); }

async function refreshResources() {
  await fetch('/api/resources/refresh', { method: 'POST' });
  allResources = []; cnSet = new Set();
  await loadResources();
}

// ── Detail panel ──────────────────────────────────────────────────────────────

async function selectResource(name, version, versions) {
  selectedResource = name;
  renderTable();

  document.getElementById('detail-placeholder').style.display = 'none';
  const panel = document.getElementById('detail-panel');
  panel.style.display = '';

  document.getElementById('dp-name').textContent = name;
  document.getElementById('dp-versions').textContent = 'Available: v' + (versions || version);

  // Badges
  const isCn = cnSet.has(name);
  const ann = annotationMap[name];
  document.getElementById('dp-badges').innerHTML = [
    isCn ? '<span class="badge bg-success">CN ✓</span>' : '<span class="badge bg-secondary">CN —</span>',
    isCn ? '' : '',
  ].join('');

  // Populate annotation fields
  document.getElementById('dp-notes').value = ann?.notes || '';
  document.getElementById('dp-gap-check').checked = !!(ann?.trigger_conditions_gap);

  // Mnemonic matches
  loadMnemonicMatches(name);
}

async function loadMnemonicMatches(resourceName) {
  const container = document.getElementById('dp-mnemonics');
  container.innerHTML = '<div class="text-muted small">Searching...</div>';
  try {
    const r = await fetch(`/api/mnemonics/?q=${encodeURIComponent(resourceName)}`);
    const items = await r.json();
    const matches = items.filter(m => (m.eedm_resource || '').toLowerCase().includes(resourceName.toLowerCase()));
    if (!matches.length) {
      container.innerHTML = '<div class="text-muted small">No mnemonic entries match this resource. <a href="/mnemonics">Add one →</a></div>';
      return;
    }
    container.innerHTML = matches.map(m => `
      <div class="d-flex justify-content-between align-items-start border-bottom py-2">
        <div>
          <div class="fw-bold font-monospace small">${m.mnemonic}</div>
          <div class="text-muted small">${m.colleague_file || ''}</div>
          ${m.gotchas ? `<div class="mnemonic-gotcha mt-1" style="font-size:.75rem">⚠ ${m.gotchas.substring(0,120)}${m.gotchas.length > 120 ? '…' : ''}</div>` : ''}
        </div>
        <div class="text-end">
          ${m.cn_supported ? '<span class="badge bg-success" style="font-size:.65rem">CN ✓</span>' : ''}
        </div>
      </div>`).join('');
  } catch (e) {
    container.innerHTML = `<div class="text-danger small">Error: ${e.message}</div>`;
  }
}

// ── Postman Export ────────────────────────────────────────────────────────────

function exportPostmanCollection() {
  if (!allResources.length) {
    alert('No resources loaded — click the refresh button first.');
    return;
  }

  const items = allResources.map(r => {
    const name = resourceName(r);
    const ver = r.latestVersion || r.version || '';
    const accept = ver
      ? `application/vnd.hedtech.integration.v${ver}+json`
      : 'application/json';

    return {
      name,
      item: [
        {
          name: `List ${name}`,
          request: {
            method: 'GET',
            header: [{ key: 'Accept', value: accept }],
            url: {
              raw: `{{base_url}}/api/${name}?offset=0&limit=100`,
              host: ['{{base_url}}'],
              path: ['api', name],
              query: [{ key: 'offset', value: '0' }, { key: 'limit', value: '100' }],
            },
          },
        },
        {
          name: `Get ${name} by ID`,
          request: {
            method: 'GET',
            header: [{ key: 'Accept', value: accept }],
            url: {
              raw: `{{base_url}}/api/${name}/:id`,
              host: ['{{base_url}}'],
              path: ['api', name, ':id'],
              variable: [{ key: 'id', value: '', description: 'GUID' }],
            },
          },
        },
      ],
    };
  });

  const collection = {
    info: {
      name: 'Doane Ethos API',
      schema: 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json',
    },
    auth: {
      type: 'bearer',
      bearer: [{ key: 'token', value: '{{ethos_token}}', type: 'string' }],
    },
    variable: [
      { key: 'base_url', value: 'https://integrate.elluciancloud.com' },
      { key: 'ethos_token', value: '', description: 'JWT from POST /auth with your Ethos API key' },
    ],
    item: items,
  };

  const blob = new Blob([JSON.stringify(collection, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'doane-ethos-api.postman_collection.json';
  a.click();
  URL.revokeObjectURL(a.href);
}

async function saveAnnotation() {
  if (!selectedResource) return;

  const confirmed = await confirmAction({
    title: 'Save annotation',
    message: 'Save the annotation for "' + selectedResource + '"?',
    confirmLabel: 'Save',
  });
  if (!confirmed) return;

  const btn = document.querySelector('[onclick="saveAnnotation()"]');
  btn.disabled = true;

  const body = {
    notes: document.getElementById('dp-notes').value || null,
    trigger_conditions_gap: document.getElementById('dp-gap-check').checked,
    updated_by: 'console',
  };

  try {
    const r = await fetch(`/api/resources/${encodeURIComponent(selectedResource)}/annotate`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await r.json();
    annotationMap[selectedResource] = data;
    renderTable();

    const status = document.getElementById('dp-save-status');
    status.textContent = '✓ Saved';
    status.className = 'small text-success ms-2';
    setTimeout(() => { status.textContent = ''; }, 2500);

    // Refresh gap badge
    document.getElementById('dp-badges').innerHTML = [
      cnSet.has(selectedResource) ? '<span class="badge bg-success">CN ✓</span>' : '<span class="badge bg-secondary">CN —</span>',
      data.trigger_conditions_gap ? '<span class="badge bg-warning text-dark">⚠ Gap</span>' : '',
    ].join('');
  } catch (e) {
    const status = document.getElementById('dp-save-status');
    status.textContent = '✗ ' + e.message;
    status.className = 'small text-danger ms-2';
  } finally {
    btn.disabled = false;
  }
}

loadResources();

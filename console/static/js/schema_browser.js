'use strict';

let allTypes = [];
let selectedType = null;

// ── Type list ─────────────────────────────────────────────────────────────────

async function loadTypes() {
  const list = document.getElementById('type-list');
  list.innerHTML = '<div class="text-muted small text-center py-2"><span class="spinner-border spinner-border-sm"></span></div>';

  try {
    const r = await fetch('/api/schema-browser/types');
    const data = await r.json();
    if (data.error) throw new Error(data.error);
    allTypes = data.items || [];
    document.getElementById('type-count').textContent = `${allTypes.length} resources`;
    renderTypeList(allTypes);
  } catch (e) {
    list.innerHTML = `<div class="text-danger small px-2">${e.message}</div>`;
  }
}

function renderTypeList(items) {
  const list = document.getElementById('type-list');
  if (!items.length) {
    list.innerHTML = '<div class="text-muted small px-2">No types found.</div>';
    return;
  }
  list.innerHTML = items.map(t =>
    `<div class="schema-resource-header ${selectedType === t.name ? 'active-type' : ''}"
          onclick="selectType('${t.name}')" style="cursor:pointer">
       <i class="bi bi-braces-asterisk me-1" style="font-size:.65rem;color:#6c757d"></i>
       ${t.name}
     </div>`
  ).join('');
}

function filterTypes() {
  const q = document.getElementById('type-search').value.toLowerCase();
  const filtered = q ? allTypes.filter(t => t.name.toLowerCase().includes(q)) : allTypes;
  renderTypeList(filtered);
}

// ── Field detail ──────────────────────────────────────────────────────────────

async function selectType(typeName) {
  selectedType = typeName;
  renderTypeList(allTypes.filter(t => {
    const q = document.getElementById('type-search').value.toLowerCase();
    return !q || t.name.toLowerCase().includes(q);
  }));

  document.getElementById('fields-header').textContent = typeName;
  const panel = document.getElementById('fields-panel');
  panel.innerHTML = '<div class="text-muted small text-center py-2"><span class="spinner-border spinner-border-sm"></span></div>';

  try {
    const r = await fetch(`/api/schema-browser/type/${encodeURIComponent(typeName)}`);
    const data = await r.json();
    if (data.error) throw new Error(data.error);

    if (!data.fields?.length) {
      panel.innerHTML = '<div class="text-muted small px-1">No fields found.</div>';
      return;
    }

    panel.innerHTML = `
      <div class="table-responsive">
        <table class="table table-sm resource-table mb-0">
          <thead><tr>
            <th>Field</th><th>Type</th><th style="width:60px">Req.</th>
          </tr></thead>
          <tbody>
            ${data.fields.map(f => `
              <tr>
                <td class="font-monospace small">${f.name}</td>
                <td><span class="field-type-badge">${f.type}</span></td>
                <td class="text-center">${f.nullable ? '' : '<i class="bi bi-asterisk text-danger" style="font-size:.6rem" title="Non-null"></i>'}</td>
              </tr>`).join('')}
          </tbody>
        </table>
      </div>
      <div class="text-muted small mt-1">${data.fields.length} fields</div>`;

    // Pre-fill validator resource field
    document.getElementById('val-resource').value = typeName.replace(/\d+$/, '').toLowerCase();
  } catch (e) {
    panel.innerHTML = `<div class="text-danger small">${e.message}</div>`;
  }
}

// ── Validator ─────────────────────────────────────────────────────────────────

async function validatePayload() {
  const resource = document.getElementById('val-resource').value.trim();
  const version = document.getElementById('val-version').value.trim();
  const payloadText = document.getElementById('val-payload').value.trim();
  const result = document.getElementById('val-result');

  if (!resource) { result.innerHTML = '<div class="text-danger small">Enter a resource name.</div>'; return; }
  if (!payloadText) { result.innerHTML = '<div class="text-danger small">Paste a payload to validate.</div>'; return; }

  let payload;
  try { payload = JSON.parse(payloadText); } catch {
    result.innerHTML = '<div class="text-danger small">Payload must be valid JSON.</div>'; return;
  }

  result.innerHTML = '<div class="text-muted small"><span class="spinner-border spinner-border-sm me-1"></span>Validating…</div>';

  try {
    const r = await fetch('/api/schema-browser/validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ resource, version: version || undefined, payload }),
    });
    const data = await r.json();

    if (data.error) {
      result.innerHTML = `<div class="text-danger small">✗ ${data.error}</div>`;
      return;
    }

    if (data.valid) {
      result.innerHTML = '<div class="small text-success p-2 rounded" style="background:#d4edda"><i class="bi bi-check-circle-fill me-1"></i>Valid — payload conforms to EEDM schema.</div>';
      return;
    }

    result.innerHTML = `
      <div class="small text-danger fw-semibold mb-1">✗ ${data.error_count} validation error${data.error_count !== 1 ? 's' : ''}</div>
      ${data.errors.map(e => `
        <div class="border-bottom py-1">
          <div class="font-monospace" style="font-size:.72rem;color:#1F3864">${e.path}</div>
          <div class="text-muted" style="font-size:.72rem">${e.message}</div>
        </div>`).join('')}
      ${data.error_count > 50 ? `<div class="text-muted small mt-1">… and ${data.error_count - 50} more</div>` : ''}`;
  } catch (e) {
    result.innerHTML = `<div class="text-danger small">Network error: ${e.message}</div>`;
  }
}

function formatPayload() {
  const ta = document.getElementById('val-payload');
  try {
    ta.value = JSON.stringify(JSON.parse(ta.value), null, 2);
  } catch { /* ignore */ }
}

// ── Init ──────────────────────────────────────────────────────────────────────
// Server-side cache makes this cheap on repeat visits — auto-load so the
// tab doesn't require a manual click to populate.
loadTypes();

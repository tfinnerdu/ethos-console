'use strict';

let diffResources = [];
let selectedDiffResource = null;

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s == null ? '' : String(s);
  return d.innerHTML;
}

async function loadDiffResources() {
  const list = document.getElementById('diff-resource-list');
  if (!list) return;
  list.innerHTML = '<div class="text-muted small text-center py-2"><span class="spinner-border spinner-border-sm"></span></div>';

  try {
    const r = await fetch('/api/resources/');
    const data = await r.json();
    diffResources = (data.items || []).map(r => r.name || r.resourceName).filter(Boolean).sort();
    if (!diffResources.length && data.error) {
      list.innerHTML = `<div class="text-danger small px-2">Could not load resources — ${esc(data.error)}</div>`;
      return;
    }
    renderDiffList(diffResources);
  } catch (e) {
    list.innerHTML = `<div class="text-danger small px-2">${esc(e.message)}</div>`;
  }
}

function renderDiffList(items) {
  const list = document.getElementById('diff-resource-list');
  list.innerHTML = items.map(name =>
    `<div class="schema-resource-header ${selectedDiffResource === name ? 'active-type' : ''}"
          onclick="runDiff('${name}')" style="cursor:pointer;font-size:.78rem">${name}</div>`
  ).join('');
}

function filterDiffResources() {
  const q = document.getElementById('diff-search').value.toLowerCase();
  renderDiffList(q ? diffResources.filter(n => n.toLowerCase().includes(q)) : diffResources);
}

async function runDiff(resource) {
  selectedDiffResource = resource;
  filterDiffResources();
  document.getElementById('diff-title').textContent = `Field Diff: ${resource}`;
  const panel = document.getElementById('diff-panel');
  panel.innerHTML = '<div class="text-muted small text-center py-2"><span class="spinner-border spinner-border-sm"></span></div>';

  try {
    const r = await fetch(`/api/phase3/field-diff/${encodeURIComponent(resource)}`);
    const data = await r.json();

    if (data.error) { panel.innerHTML = `<div class="text-danger small">${data.error}</div>`; return; }

    document.getElementById('badge-matched').textContent  = `${data.matched?.length ?? 0} matched`;
    document.getElementById('badge-eedm-only').textContent = `${data.eedm_only?.length ?? 0} EEDM-only`;
    document.getElementById('badge-ud-only').textContent   = `${data.unidata_only?.length ?? 0} UniData-only`;

    if (data.note) {
      panel.innerHTML = `<div class="alert alert-info small py-2">${data.note}</div>`;
      return;
    }

    const rows = [
      ...(data.matched || []).map(f => ({ field: f, status: 'matched' })),
      ...(data.eedm_only || []).map(f => ({ field: f, status: 'eedm' })),
      ...(data.unidata_only || []).map(f => ({ field: f, status: 'ud' })),
    ];

    panel.innerHTML = `
      <div class="table-responsive">
        <table class="table table-sm resource-table mb-0">
          <thead><tr><th>Field</th><th>EEDM</th><th>UniData</th><th>Status</th></tr></thead>
          <tbody>
            ${rows.map(({ field, status }) => `
              <tr>
                <td class="font-monospace small">${field}</td>
                <td class="text-center">${status !== 'ud'  ? '<i class="bi bi-check-circle-fill text-success"></i>' : '<i class="bi bi-dash text-muted"></i>'}</td>
                <td class="text-center">${status !== 'eedm' ? '<i class="bi bi-check-circle-fill text-success"></i>' : '<i class="bi bi-dash text-muted"></i>'}</td>
                <td>${status === 'matched' ? '<span class="badge badge-active" style="font-size:.62rem">Aligned</span>'
                    : status === 'eedm'    ? '<span class="badge badge-error"  style="font-size:.62rem">EEDM only</span>'
                    :                        '<span class="badge badge-silent" style="font-size:.62rem">UniData only</span>'}</td>
              </tr>`).join('')}
          </tbody>
        </table>
      </div>`;
  } catch (e) {
    panel.innerHTML = `<div class="text-danger small">${e.message}</div>`;
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('diff-resource-list')) loadDiffResources();
});

'use strict';

let allFiles = [];
let queryResults = [];

async function loadFiles() {
  const list = document.getElementById('cq-file-list');
  if (!list) return;
  list.innerHTML = '<div class="text-center py-2"><span class="spinner-border spinner-border-sm"></span></div>';
  try {
    const r = await fetch('/api/phase3/colleague-files');
    const data = await r.json();
    allFiles = data.items || [];
    renderFiles(allFiles);
    if (data.note) {
      list.innerHTML += `<div class="text-muted small px-1 mt-1">${data.note}</div>`;
    }
  } catch (e) {
    list.innerHTML = `<div class="text-danger small px-1">${e.message}</div>`;
  }
}

function renderFiles(items) {
  const list = document.getElementById('cq-file-list');
  if (!items.length) {
    list.innerHTML = '<div class="text-muted small text-center py-2">No files found.</div>';
    return;
  }
  list.innerHTML = items.map(f =>
    `<div class="schema-resource-header" onclick="insertFile('${f}')" style="cursor:pointer;font-size:.75rem">${f}</div>`
  ).join('');
}

function filterFiles() {
  const q = document.getElementById('cq-file-search').value.toLowerCase();
  renderFiles(q ? allFiles.filter(f => f.toLowerCase().includes(q)) : allFiles);
}

function insertFile(name) {
  const ta = document.getElementById('cq-statement');
  const val = ta.value;
  if (!val.trim()) {
    ta.value = `SELECT ID FROM ${name} `;
  } else {
    ta.value = val + name;
  }
  ta.focus();
}

async function runQuery() {
  const statement = document.getElementById('cq-statement').value.trim();
  if (!statement) return;

  const btn = document.getElementById('btn-run-query');
  const meta = document.getElementById('cq-meta');
  const results = document.getElementById('cq-results');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Running…';
  meta.textContent = '';
  results.innerHTML = '<div class="text-muted small text-center py-2">Running…</div>';

  const t0 = Date.now();
  try {
    const r = await fetch('/api/phase3/colleague-query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ statement }),
    });
    const data = await r.json();
    const elapsed = Date.now() - t0;

    if (data.error) { results.innerHTML = `<div class="text-danger small">${data.error}<br><small class="text-muted">${data.setup || ''}</small></div>`; return; }

    if (data.note) { results.innerHTML = `<div class="alert alert-info small py-2">${data.note}</div>`; return; }

    queryResults = data.rows || [];
    meta.textContent = `${data.row_count} rows · ${elapsed}ms`;
    document.getElementById('btn-export-cq').style.display = data.row_count ? '' : 'none';

    if (!data.columns?.length) {
      results.innerHTML = '<div class="text-muted small text-center py-2">No results.</div>';
      return;
    }

    results.innerHTML = `
      <div class="table-responsive" style="max-height:400px;overflow-y:auto">
        <table class="table table-sm resource-table mb-0">
          <thead><tr>${data.columns.map(c => `<th>${c}</th>`).join('')}</tr></thead>
          <tbody>
            ${data.rows.map(row =>
              `<tr>${data.columns.map(c => `<td class="small font-monospace">${row[c] ?? ''}</td>`).join('')}</tr>`
            ).join('')}
          </tbody>
        </table>
      </div>`;
  } catch (e) {
    results.innerHTML = `<div class="text-danger small">Network error: ${e.message}</div>`;
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-play-fill me-1"></i>Run';
  }
}

function clearQuery() {
  document.getElementById('cq-statement').value = '';
  document.getElementById('cq-results').innerHTML = '<div class="text-muted small text-center py-4">Run a query to see results.</div>';
  document.getElementById('cq-meta').textContent = '';
  document.getElementById('btn-export-cq').style.display = 'none';
  queryResults = [];
}

function exportResults() {
  if (!queryResults.length) return;
  const keys = Object.keys(queryResults[0]);
  const csv = [keys.join(','),
    ...queryResults.map(r => keys.map(k => JSON.stringify(r[k] ?? '')).join(','))
  ].join('\n');
  const a = document.createElement('a');
  a.href = 'data:text/csv,' + encodeURIComponent(csv);
  a.download = 'colleague_query.csv';
  a.click();
}

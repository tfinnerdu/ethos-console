'use strict';

let allFiles = [];
let queryResults = [];

function escapeHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

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

  const verb = statement.split(/\s+/)[0].toUpperCase();
  const confirmed = await confirmAction({
    title: 'Run direct Colleague statement',
    message: 'This runs the statement below directly against Colleague (UniData):\n\n'
      + statement + '\n\n'
      + 'UniData has no transaction rollback. A write verb (DELETE, CLEAR.FILE, etc.) '
      + 'changes data immediately. Type the command verb to confirm.',
    confirmLabel: 'Run statement',
    danger: true,
    requireText: verb,
  });
  if (!confirmed) return;

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

    if (data.error) { results.innerHTML = `<div class="text-danger small">${escapeHtml(data.error)}<br><small class="text-muted">${escapeHtml(data.setup || '')}</small></div>`; return; }

    if (data.note) { results.innerHTML = `<div class="alert alert-info small py-2">${escapeHtml(data.note)}</div>`; return; }

    // Raw TCL output (uopy command response)
    if (data.output !== undefined) {
      meta.textContent = `${elapsed}ms`;
      results.innerHTML = data.output
        ? `<pre class="small font-monospace mb-0" style="max-height:420px;overflow:auto;white-space:pre-wrap">${escapeHtml(data.output)}</pre>`
        : '<div class="text-muted small text-center py-2">No output.</div>';
      return;
    }

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
          <thead><tr>${data.columns.map(c => `<th>${escapeHtml(c)}</th>`).join('')}</tr></thead>
          <tbody>
            ${data.rows.map(row =>
              `<tr>${data.columns.map(c => `<td class="small font-monospace">${escapeHtml(row[c] ?? '')}</td>`).join('')}</tr>`
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

// ── Syntax Reference ──────────────────────────────────────────────────────────

function toggleSyntaxRef() {
  const card = document.getElementById('syntax-ref-card');
  card.style.display = card.style.display === 'none' ? '' : 'none';
}

// ── Snippet Insertion ─────────────────────────────────────────────────────────

const _SNIPPETS = {
  select:  'SELECT @ID FROM FILE WITH FIELD = "VALUE"',
  list:    'LIST FILE FIELD1 FIELD2 WITH FIELD1 = "VALUE" SAMPLE 20',
  count:   'COUNT FILE WITH FIELD = "VALUE"',
  saving:  'SELECT FILE WITH FIELD = "VALUE" SAVING @ID',
  sample:  'LIST FILE FIELD1 FIELD2 SAMPLE 10',
  voc:     'LIST VOC WITH F1 = "F" BY @ID',
};

function insertSnippet(name) {
  const ta = document.getElementById('cq-statement');
  if (!ta) return;
  ta.value = _SNIPPETS[name] || name;
  ta.focus();
  ta.setSelectionRange(ta.value.length, ta.value.length);
}

// ── Subroutine Caller ─────────────────────────────────────────────────────────

let _subArgCount = 0;

function toggleSubPanel() {
  const panel = document.getElementById('sub-panel');
  const chevron = document.getElementById('sub-chevron');
  const open = panel.style.display === 'none';
  panel.style.display = open ? '' : 'none';
  chevron.style.transform = open ? 'rotate(180deg)' : '';
}

function addSubArg() {
  const container = document.getElementById('sub-args');
  const idx = _subArgCount++;
  const row = document.createElement('div');
  row.className = 'row g-1 mb-1 align-items-center';
  row.id = `sub-arg-row-${idx}`;
  row.innerHTML = `
    <div class="col-auto" style="width:3rem">
      <span class="text-muted small font-monospace">A${idx + 1}</span>
    </div>
    <div class="col-3">
      <input type="text" class="form-control form-control-sm font-monospace sub-arg-label"
             placeholder="Label" style="font-size:.75rem" />
    </div>
    <div class="col-2">
      <select class="form-select form-select-sm sub-arg-dir" style="font-size:.75rem">
        <option value="in">IN</option>
        <option value="out">OUT</option>
        <option value="inout">INOUT</option>
      </select>
    </div>
    <div class="col">
      <input type="text" class="form-control form-control-sm font-monospace sub-arg-val"
             placeholder="Value" style="font-size:.75rem" />
    </div>
    <div class="col-auto">
      <button class="btn btn-sm btn-outline-danger py-0" onclick="removeSubArg(this)"
              style="font-size:.7rem">✕</button>
    </div>`;
  container.appendChild(row);
}

function removeSubArg(btn) {
  btn.closest('[id^="sub-arg-row-"]').remove();
}

async function callSubroutine() {
  const name = document.getElementById('sub-name').value.trim().toUpperCase();
  if (!name) {
    document.getElementById('sub-result').innerHTML =
      '<div class="text-warning small">Enter a subroutine name.</div>';
    return;
  }

  const confirmed = await confirmAction({
    title: 'Call Colleague subroutine',
    message: 'This calls Colleague subroutine "' + name + '" directly.\n\n'
      + 'Subroutines can read or write Colleague data and have no rollback. '
      + 'Type the subroutine name to confirm.',
    confirmLabel: 'Call subroutine',
    danger: true,
    requireText: name,
  });
  if (!confirmed) return;

  const argRows = document.querySelectorAll('#sub-args [id^="sub-arg-row-"]');
  const args = Array.from(argRows).map(row => ({
    label: row.querySelector('.sub-arg-label').value.trim() || undefined,
    direction: row.querySelector('.sub-arg-dir').value,
    value: row.querySelector('.sub-arg-val').value,
  }));

  const btn = document.getElementById('btn-sub-call');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Calling…';

  const t0 = Date.now();
  try {
    const r = await fetch('/api/phase3/subroutine', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, args }),
    });
    const data = await r.json();
    const elapsed = Date.now() - t0;
    document.getElementById('sub-meta').textContent = `${elapsed}ms`;

    if (data.error) {
      document.getElementById('sub-result').innerHTML =
        `<div class="text-danger small">${escapeHtml(data.error)}<br><small class="text-muted">${escapeHtml(data.setup || '')}</small></div>`;
      return;
    }

    const rows = (data.args || []).map(a => {
      const dir = a.direction.toUpperCase();
      const dirBadge = dir === 'OUT' || dir === 'INOUT'
        ? `<span class="badge bg-primary me-1" style="font-size:.6rem">${dir}</span>`
        : `<span class="badge bg-secondary me-1" style="font-size:.6rem">${dir}</span>`;
      const label = a.label || `A${a.index + 1}`;
      return `<tr>
        <td class="font-monospace small pe-2">${escapeHtml(label)}</td>
        <td>${dirBadge}</td>
        <td class="font-monospace small" style="max-width:320px;word-break:break-all">${escapeHtml(a.value)}</td>
      </tr>`;
    }).join('');

    document.getElementById('sub-result').innerHTML = rows
      ? `<table class="table table-sm resource-table mb-0">
           <thead><tr><th>Arg</th><th>Dir</th><th>Value</th></tr></thead>
           <tbody>${rows}</tbody>
         </table>`
      : '<div class="text-muted small text-center py-2">Subroutine called (no args).</div>';
  } catch (e) {
    document.getElementById('sub-result').innerHTML =
      `<div class="text-danger small">Network error: ${escapeHtml(e.message)}</div>`;
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-play-fill me-1"></i>Call';
  }
}

function clearSubroutine() {
  document.getElementById('sub-name').value = '';
  document.getElementById('sub-args').innerHTML = '';
  document.getElementById('sub-result').innerHTML = '';
  document.getElementById('sub-meta').textContent = '';
  _subArgCount = 0;
}

// ── Init ──────────────────────────────────────────────────────────────────────
// Auto-load the files list so the tab doesn't require a manual click.
// Wraps in DOMContentLoaded because the file-list container is inside the
// configured-only branch of the template.
document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('cq-file-list')) loadFiles();
});

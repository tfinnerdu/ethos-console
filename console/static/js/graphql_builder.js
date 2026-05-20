'use strict';

// ── State ─────────────────────────────────────────────────────────────────────
let schemaData = null;
let selectedFields = {};   // { resourceType: Set<fieldPath> }
let currentResource = null;
let saveModal = null;

// ── Schema loading ────────────────────────────────────────────────────────────

async function loadSchema(forceRefresh = false) {
  const btn = document.getElementById('btn-load-schema');
  const status = document.getElementById('schema-status');
  btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
  status.textContent = 'Loading...';

  try {
    if (forceRefresh) {
      await fetch('/api/graphql-console/schema', { method: 'DELETE' });
    }
    const r = await fetch('/api/graphql-console/schema');
    const data = await r.json();
    if (data.error) throw new Error(data.error);
    schemaData = data;
    renderSchemaTree(data);
    status.textContent = `${countQueryFields(data)} EEDM types loaded`;
  } catch (e) {
    status.textContent = '✗ ' + e.message;
    document.getElementById('schema-tree').innerHTML =
      `<div class="text-danger small p-2">Schema load failed: ${e.message}</div>`;
  } finally {
    btn.innerHTML = '<i class="bi bi-arrow-clockwise"></i>';
  }
}

function countQueryFields(schema) {
  const queryTypeName = schema.queryType?.name || 'Query';
  const queryType = (schema.types || []).find(t => t.name === queryTypeName);
  return queryType?.fields?.length || 0;
}

function renderSchemaTree(schema) {
  const queryTypeName = schema.queryType?.name || 'Query';
  const typeMap = buildTypeMap(schema.types || []);
  const queryType = typeMap[queryTypeName];
  if (!queryType) {
    document.getElementById('schema-tree').innerHTML = '<div class="text-muted small p-2">No query type found in schema.</div>';
    return;
  }

  const fields = (queryType.fields || []).sort((a, b) => a.name.localeCompare(b.name));
  const tree = document.getElementById('schema-tree');
  tree.innerHTML = '';

  fields.forEach(field => {
    const section = buildResourceSection(field, typeMap);
    tree.appendChild(section);
  });
}

function buildTypeMap(types) {
  const map = {};
  types.forEach(t => { map[t.name] = t; });
  return map;
}

function getTypeName(typeRef) {
  if (!typeRef) return null;
  if (typeRef.name) return typeRef.name;
  return getTypeName(typeRef.ofType);
}

function buildResourceSection(field, typeMap) {
  const div = document.createElement('div');
  div.className = 'mb-1';
  div.dataset.resource = field.name;

  const header = document.createElement('div');
  header.className = 'schema-resource-header';
  header.innerHTML = `<i class="bi bi-chevron-right" id="chevron-${field.name}" style="font-size:.65rem;transition:transform .15s"></i>
    <span>${field.name}</span>`;
  header.onclick = () => toggleResource(field.name, div, field, typeMap);
  div.appendChild(header);

  const body = document.createElement('div');
  body.id = `res-body-${field.name}`;
  body.style.display = 'none';
  div.appendChild(body);

  return div;
}

function toggleResource(name, div, field, typeMap) {
  const body = div.querySelector(`#res-body-${name}`);
  const chevron = div.querySelector(`#chevron-${name}`);
  const isOpen = body.style.display !== 'none';

  if (isOpen) {
    body.style.display = 'none';
    chevron.style.transform = '';
  } else {
    body.style.display = '';
    chevron.style.transform = 'rotate(90deg)';
    if (!body.hasChildNodes()) {
      populateFields(name, body, field, typeMap);
    }
  }
}

function populateFields(resourceName, container, field, typeMap) {
  const nodeFields = getNodeFields(field, typeMap);
  if (!nodeFields.length) {
    container.innerHTML = '<div class="text-muted small ps-4">No fields found</div>';
    return;
  }

  nodeFields.forEach(f => {
    const row = document.createElement('div');
    row.className = 'schema-field-row';
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.id = `field-${resourceName}-${f.name}`;
    cb.dataset.resource = resourceName;
    cb.dataset.field = f.name;
    cb.addEventListener('change', () => onFieldToggle(resourceName, f.name, cb.checked));

    if (selectedFields[resourceName]?.has(f.name)) cb.checked = true;

    const typeName = getTypeName(f.type) || '';
    row.innerHTML = '';
    row.appendChild(cb);
    row.insertAdjacentHTML('beforeend',
      `<label for="field-${resourceName}-${f.name}" style="cursor:pointer;flex:1">${f.name}</label>
       <span class="field-type-badge">${typeName}</span>`);
    container.appendChild(row);
  });
}

function getNodeFields(field, typeMap) {
  const returnTypeName = getTypeName(field.type);
  if (!returnTypeName) return [];
  const returnType = typeMap[returnTypeName];
  if (!returnType) return [];

  const edgesField = (returnType.fields || []).find(f => f.name === 'edges');
  if (!edgesField) return returnType.fields || [];

  const edgesTypeName = getTypeName(edgesField.type);
  const edgesType = typeMap[edgesTypeName];
  if (!edgesType) return [];

  const nodeField = (edgesType.fields || []).find(f => f.name === 'node');
  if (!nodeField) return [];

  const nodeTypeName = getTypeName(nodeField.type);
  const nodeType = typeMap[nodeTypeName];
  return nodeType?.fields || [];
}

function onFieldToggle(resourceName, fieldName, checked) {
  if (!selectedFields[resourceName]) selectedFields[resourceName] = new Set();
  if (checked) {
    selectedFields[resourceName].add(fieldName);
  } else {
    selectedFields[resourceName].delete(fieldName);
  }
  rebuildQuery(resourceName);
}

function rebuildQuery(resourceName) {
  const fields = selectedFields[resourceName];
  if (!fields || !fields.size) {
    document.getElementById('query-editor').value = '';
    return;
  }

  const fieldList = Array.from(fields).join('\n        ');
  const query = `query {
  ${resourceName} {
    edges {
      node {
        id
        ${fieldList}
      }
    }
  }
}`;
  document.getElementById('query-editor').value = query;
}

function filterSchema() {
  const q = document.getElementById('schema-search').value.toLowerCase();
  document.querySelectorAll('#schema-tree > div[data-resource]').forEach(div => {
    const name = (div.dataset.resource || '').toLowerCase();
    div.style.display = (!q || name.includes(q)) ? '' : 'none';
  });
}

// ── Query execution ───────────────────────────────────────────────────────────

async function runQuery() {
  const query = document.getElementById('query-editor').value.trim();
  if (!query) return;

  const varsText = document.getElementById('vars-editor').value.trim();
  let variables = {};
  try { variables = varsText ? JSON.parse(varsText) : {}; } catch {
    setResult('Variables must be valid JSON', true); return;
  }

  const btn = document.getElementById('btn-run');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Running...';
  setResult('Running...', false);

  const t0 = Date.now();
  try {
    const r = await fetch('/api/graphql-console/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, variables }),
    });
    const data = await r.json();
    const elapsed = Date.now() - t0;
    document.getElementById('result-meta').textContent = `${elapsed}ms`;
    setResult(JSON.stringify(data, null, 2), !r.ok || data.errors);
    document.getElementById('btn-copy-result').disabled = false;
  } catch (e) {
    setResult('Network error: ' + e.message, true);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-play-fill me-1"></i>Run';
  }
}

function setResult(text, isError) {
  const el = document.getElementById('result-display');
  el.textContent = text;
  el.style.color = isError ? '#f85149' : '#c9d1d9';
}

function copyResult() {
  const text = document.getElementById('result-display').textContent;
  navigator.clipboard.writeText(text).then(() => {
    const btn = document.getElementById('btn-copy-result');
    btn.innerHTML = '<i class="bi bi-check-lg"></i>';
    setTimeout(() => { btn.innerHTML = '<i class="bi bi-clipboard"></i>'; }, 1500);
  });
}

function copyCurl() {
  const query = document.getElementById('query-editor').value;
  const varsText = document.getElementById('vars-editor').value || '{}';
  let variables = {};
  try { variables = JSON.parse(varsText); } catch { alert('Variables must be valid JSON before copying curl'); return; }
  const body = JSON.stringify({ query, variables });
  const curl = `curl -X POST https://integrate.elluciancloud.com/graphql \\\n  -H "Authorization: Bearer <ethos_jwt_token>" \\\n  -H "Content-Type: application/json" \\\n  -d '${body}'`;
  navigator.clipboard.writeText(curl).then(() => alert('curl command copied to clipboard'));
}

function clearQuery() {
  document.getElementById('query-editor').value = '';
  document.getElementById('vars-editor').value = '{}';
  document.getElementById('result-display').textContent = 'Run a query to see results.';
  document.getElementById('btn-copy-result').disabled = true;
  document.getElementById('result-meta').textContent = '';
  selectedFields = {};
  document.querySelectorAll('#schema-tree input[type=checkbox]').forEach(cb => { cb.checked = false; });
}

function formatQuery() {
  const raw = document.getElementById('query-editor').value;
  try {
    const lines = raw.split('\n').map(l => l.trim()).filter(Boolean);
    document.getElementById('query-editor').value = lines.join('\n');
  } catch { /* ignore */ }
}

// ── Saved queries ─────────────────────────────────────────────────────────────

let savedQueries = [];

async function loadSavedQueries() {
  try {
    const r = await fetch('/api/graphql-console/saved');
    const data = await r.json();
    savedQueries = data.items ?? (Array.isArray(data) ? data : []);
    renderSavedChips();
  } catch (e) {
    document.getElementById('saved-chips').innerHTML = '<span class="text-muted small">Error loading</span>';
  }
}

function renderSavedChips() {
  const container = document.getElementById('saved-chips');
  if (!savedQueries.length) {
    container.innerHTML = '<span class="text-muted small">No saved queries</span>';
    return;
  }
  container.innerHTML = savedQueries.map(q =>
    `<span class="chip-saved ${q.is_preloaded ? 'preloaded' : ''}" onclick="loadSavedQuery(${q.id})" title="${q.description || q.name}">
      ${q.is_preloaded ? '<i class="bi bi-star-fill" style="font-size:.6rem"></i>' : ''}
      ${q.name}
      ${!q.is_preloaded ? `<i class="bi bi-x" onclick="event.stopPropagation();deleteQuery(${q.id})" style="opacity:.5"></i>` : ''}
    </span>`
  ).join('');
}

function loadSavedQuery(id) {
  const q = savedQueries.find(x => x.id === id);
  if (!q) return;
  document.getElementById('query-editor').value = q.query_text;
  document.getElementById('vars-editor').value = q.variables
    ? JSON.stringify(q.variables, null, 2) : '{}';
}

function openSaveModal() {
  saveModal = saveModal || new bootstrap.Modal(document.getElementById('saveModal'));
  document.getElementById('save-name').value = '';
  document.getElementById('save-desc').value = '';
  saveModal.show();
}

async function saveCurrentQuery() {
  const name = document.getElementById('save-name').value.trim();
  const desc = document.getElementById('save-desc').value.trim();
  const query_text = document.getElementById('query-editor').value;
  const varsText = document.getElementById('vars-editor').value.trim();
  let variables = {};
  try { variables = varsText ? JSON.parse(varsText) : {}; } catch { /* ignore */ }

  if (!name) { alert('Name is required'); return; }

  await fetch('/api/graphql-console/saved', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description: desc, query_text, variables }),
  });
  saveModal.hide();
  await loadSavedQueries();
}

async function deleteQuery(id) {
  if (!confirm('Delete this saved query?')) return;
  await fetch(`/api/graphql-console/saved/${id}`, { method: 'DELETE' });
  await loadSavedQueries();
}

// ── Init ──────────────────────────────────────────────────────────────────────
loadSavedQueries();

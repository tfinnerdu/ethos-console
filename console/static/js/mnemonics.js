'use strict';

let allMnemonics = [];
let selectedId = null;
let addModal = null;

async function loadMnemonics(q) {
  const url = q ? `/api/mnemonics/?q=${encodeURIComponent(q)}` : '/api/mnemonics/';
  const r = await fetch(url);
  allMnemonics = await r.json();
  renderList();
}

function renderList() {
  const container = document.getElementById('mnemonic-list');
  if (!allMnemonics.length) {
    container.innerHTML = '<div class="text-muted text-center py-3">No results</div>';
    return;
  }
  container.innerHTML = allMnemonics.map(m => `
    <div class="mnemonic-card mb-2" onclick="showDetail(${m.id})">
      <div class="d-flex justify-content-between align-items-start">
        <div class="mnemonic-title">${m.mnemonic}</div>
        ${m.cn_supported
          ? '<span class="badge bg-success" style="font-size:.65rem">CN ✓</span>'
          : '<span class="badge bg-secondary" style="font-size:.65rem">CN —</span>'}
      </div>
      <div class="mnemonic-file">${m.colleague_file || '—'}</div>
      ${m.eedm_resource
        ? `<div class="mnemonic-resource">${m.eedm_resource}${m.eedm_version ? ' v'+m.eedm_version : ''}</div>`
        : ''}
    </div>`).join('');
}

function showDetail(id) {
  selectedId = id;
  const m = allMnemonics.find(x => x.id === id);
  if (!m) return;

  document.getElementById('detail-panel').style.display = '';
  document.getElementById('detail-placeholder').style.display = 'none';
  document.getElementById('detail-mnemonic').textContent = m.mnemonic;
  document.getElementById('detail-file').textContent = m.colleague_file || '—';
  document.getElementById('detail-resource').textContent = m.eedm_resource
    ? `${m.eedm_resource}${m.eedm_version ? ' v'+m.eedm_version : ''}`
    : '—';
  document.getElementById('detail-version').textContent = m.eedm_version ? `v${m.eedm_version}` : '—';
  document.getElementById('detail-cn').innerHTML = m.cn_supported
    ? '<span class="badge bg-success">Supported</span>'
    : '<span class="badge bg-secondary">Not supported</span>';

  const cnNotesBlock = document.getElementById('detail-cn-notes-block');
  if (m.cn_notes) {
    cnNotesBlock.style.display = '';
    document.getElementById('detail-cn-notes').textContent = m.cn_notes;
  } else {
    cnNotesBlock.style.display = 'none';
  }

  const gotchaBlock = document.getElementById('detail-gotcha-block');
  if (m.gotchas) {
    gotchaBlock.style.display = '';
    document.getElementById('detail-gotcha').textContent = '⚠ ' + m.gotchas;
  } else {
    gotchaBlock.style.display = 'none';
  }

  const fieldsBlock = document.getElementById('detail-fields-block');
  const fieldMappings = m.field_mappings || [];
  if (fieldMappings.length) {
    fieldsBlock.style.display = '';
    document.getElementById('detail-fields-tbody').innerHTML = fieldMappings.map(f => `
      <tr>
        <td class="font-monospace small">${f.colleague_field || ''}</td>
        <td class="font-monospace small">${f.eedm_field || ''}</td>
        <td class="small text-muted">${f.notes || ''}</td>
      </tr>`).join('');
  } else {
    fieldsBlock.style.display = 'none';
  }

  const relatedBlock = document.getElementById('detail-related-block');
  const related = m.related_mnemonics || [];
  if (related.length) {
    relatedBlock.style.display = '';
    document.getElementById('detail-related').innerHTML = related.map(r =>
      `<span class="badge bg-light text-dark border" style="cursor:pointer" onclick="searchFor('${r}')">${r}</span>`
    ).join('');
  } else {
    relatedBlock.style.display = 'none';
  }
}

function searchFor(term) {
  document.getElementById('search-input').value = term;
  loadMnemonics(term);
}

function openEditModal() {
  if (!selectedId) return;
  const m = allMnemonics.find(x => x.id === selectedId);
  if (!m) return;

  document.getElementById('modal-title').textContent = `Edit — ${m.mnemonic}`;
  document.getElementById('edit-id').value = m.id;
  document.getElementById('form-mnemonic').value = m.mnemonic;
  document.getElementById('form-mnemonic').disabled = true;
  document.getElementById('form-file').value = m.colleague_file || '';
  document.getElementById('form-resource').value = m.eedm_resource || '';
  document.getElementById('form-version').value = m.eedm_version || '';
  document.getElementById('form-cn').value = m.cn_supported ? 'true' : 'false';
  document.getElementById('form-cn-notes').value = m.cn_notes || '';
  document.getElementById('form-gotchas').value = m.gotchas || '';
  document.getElementById('form-related').value = (m.related_mnemonics || []).join(', ');

  addModal = addModal || new bootstrap.Modal(document.getElementById('addModal'));
  addModal.show();
}

async function saveMnemonic() {
  const editId = document.getElementById('edit-id').value;
  const related = document.getElementById('form-related').value
    .split(',').map(s => s.trim()).filter(Boolean);

  const body = {
    mnemonic: document.getElementById('form-mnemonic').value.toUpperCase(),
    colleague_file: document.getElementById('form-file').value || null,
    eedm_resource: document.getElementById('form-resource').value || null,
    eedm_version: document.getElementById('form-version').value || null,
    cn_supported: document.getElementById('form-cn').value === 'true',
    cn_notes: document.getElementById('form-cn-notes').value || null,
    gotchas: document.getElementById('form-gotchas').value || null,
    related_mnemonics: related,
    updated_by: 'console',
  };

  const url = editId ? `/api/mnemonics/${editId}` : '/api/mnemonics/';
  const method = editId ? 'PUT' : 'POST';

  const r = await fetch(url, {method, headers: {'Content-Type':'application/json'}, body: JSON.stringify(body)});
  if (!r.ok) {
    const err = await r.json();
    alert('Error: ' + (err.error || 'Unknown error'));
    return;
  }
  bootstrap.Modal.getInstance(document.getElementById('addModal')).hide();
  document.getElementById('edit-id').value = '';
  document.getElementById('form-mnemonic').disabled = false;
  await loadMnemonics(document.getElementById('search-input').value);
  if (editId) {
    const updated = allMnemonics.find(x => x.id === parseInt(editId));
    if (updated) showDetail(updated.id);
  }
}

async function deleteSelected() {
  if (!selectedId) return;
  const m = allMnemonics.find(x => x.id === selectedId);
  if (!m || !confirm(`Delete ${m.mnemonic}?`)) return;
  await fetch(`/api/mnemonics/${selectedId}`, {method: 'DELETE'});
  selectedId = null;
  document.getElementById('detail-panel').style.display = 'none';
  document.getElementById('detail-placeholder').style.display = '';
  await loadMnemonics(document.getElementById('search-input').value);
}

// Search debounce
let searchTimer = null;
document.getElementById('search-input').addEventListener('input', function () {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => loadMnemonics(this.value.trim()), 300);
});

// Clear modal state when hidden
document.getElementById('addModal').addEventListener('hidden.bs.modal', function () {
  document.getElementById('edit-id').value = '';
  document.getElementById('form-mnemonic').disabled = false;
  document.getElementById('modal-title').textContent = 'Add Mnemonic';
  ['form-mnemonic','form-file','form-resource','form-version','form-cn-notes','form-gotchas','form-related']
    .forEach(id => document.getElementById(id).value = '');
  document.getElementById('form-cn').value = 'false';
});

loadMnemonics();

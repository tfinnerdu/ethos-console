'use strict';

let currentPayload = null;
let currentSource = 'id';

function setSource(src) {
  currentSource = src;
  ['id', 'paste', 'build'].forEach(s => {
    document.getElementById(`src-${s}`).classList.toggle('active', s === src);
    document.getElementById(`mode-${s}`).classList.toggle('d-none', s !== src);
  });
}

async function fetchMessage() {
  const msgId = document.getElementById('message-id-input').value.trim();
  if (!msgId) return;

  const btn = document.getElementById('btn-fetch');
  btn.disabled = true;
  btn.textContent = 'Fetching...';

  try {
    const r = await fetch('api/replay/fetch', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message_id: msgId}),
    });
    const data = await r.json();
    if (!r.ok) {
      showPayload(null, `Error: ${data.error}`);
      return;
    }
    currentPayload = data.message;
    showPayload(currentPayload);
  } catch (e) {
    showPayload(null, `Network error: ${e.message}`);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-cloud-download me-1"></i>Fetch';
  }
}

function loadPasted() {
  const text = document.getElementById('paste-input').value.trim();
  try {
    currentPayload = JSON.parse(text);
    showPayload(currentPayload);
  } catch (e) {
    alert('Invalid JSON: ' + e.message);
  }
}

function buildPayload() {
  const resource = document.getElementById('build-resource').value.trim();
  const operation = document.getElementById('build-operation').value;
  const guid = document.getElementById('build-guid').value.trim();
  const contentText = document.getElementById('build-content').value.trim();

  if (!resource) { alert('Resource name is required'); return; }

  let content = {};
  try { content = contentText ? JSON.parse(contentText) : {}; } catch(e) {
    alert('Content must be valid JSON'); return;
  }

  currentPayload = {
    resource: {name: resource, id: guid, operation},
    content,
    id: Date.now(),
  };
  showPayload(currentPayload);
}

function showPayload(payload, errorText) {
  const preview = document.getElementById('payload-preview');
  const triggerBtn = document.getElementById('btn-trigger');
  const copyBtn = document.getElementById('btn-copy-json');

  if (errorText) {
    preview.textContent = errorText;
    triggerBtn.disabled = true;
    copyBtn.disabled = true;
    return;
  }

  preview.textContent = JSON.stringify(payload, null, 2);
  triggerBtn.disabled = false;
  copyBtn.disabled = false;
}

function copyJSON() {
  if (!currentPayload) return;
  navigator.clipboard.writeText(JSON.stringify(currentPayload, null, 2))
    .then(() => {
      const btn = document.getElementById('btn-copy-json');
      btn.innerHTML = '<i class="bi bi-check-lg"></i> Copied!';
      setTimeout(() => { btn.innerHTML = '<i class="bi bi-clipboard"></i> Copy JSON'; }, 2000);
    });
}

async function triggerReplay() {
  if (!currentPayload) return;

  const workflowName = document.getElementById('workflow-name').value.trim();
  const conductorUrl = document.getElementById('conductor-url').value.trim();

  if (!workflowName) { alert('Workflow name is required'); return; }
  if (!conductorUrl) { alert('Conductor URL is required'); return; }

  const confirmed = await confirmAction({
    title: 'Replay to Conductor',
    message: 'This starts a live Conductor workflow run at ' + conductorUrl + '.\n\n'
      + 'The workflow runs its full pipeline — downstream Salesforce upserts, Colleague '
      + 'writes, and notifications included. It cannot be recalled once started.',
    confirmLabel: 'Replay workflow',
    danger: true,
    requireText: workflowName,
  });
  if (!confirmed) return;

  const btn = document.getElementById('btn-trigger');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Triggering...';

  try {
    const r = await fetch('api/replay/trigger', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({payload: currentPayload, workflow_name: workflowName, conductor_url: conductorUrl}),
    });
    const data = await r.json();
    showResult(r.ok, data);
    if (r.ok) loadHistory();
  } catch (e) {
    showResult(false, {error: e.message});
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-play-fill me-1"></i>Replay to Conductor';
  }
}

function showResult(ok, data) {
  const resultDiv = document.getElementById('replay-result');
  const content = document.getElementById('replay-result-content');
  resultDiv.classList.remove('d-none');

  if (ok) {
    content.innerHTML = `<div class="alert alert-success mb-0">
      <i class="bi bi-check-circle-fill me-2"></i>
      <strong>Workflow triggered</strong> — ID: <code>${data.workflow_id}</code>
      ${data.conductor_workflow_url ? `<br><a href="${data.conductor_workflow_url}" target="_blank" class="small">Open in Conductor</a>` : ''}
    </div>`;
  } else {
    content.innerHTML = `<div class="alert alert-danger mb-0">
      <i class="bi bi-exclamation-triangle-fill me-2"></i>
      <strong>Error:</strong> ${data.error}
    </div>`;
  }
}

async function loadHistory() {
  try {
    const r = await fetch('api/replay/history');
    const data = await r.json();
    const tbody = document.getElementById('history-tbody');
    if (!data.items || !data.items.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-muted text-center py-3">No replays yet</td></tr>';
      return;
    }
    tbody.innerHTML = data.items.map(item => {
      const ts = item.replayed_at ? new Date(item.replayed_at).toLocaleString() : '—';
      const outcome = item.outcome === 'success'
        ? '<span class="badge bg-success">✓ success</span>'
        : `<span class="badge bg-danger">✗ ${item.outcome}</span>`;
      return `<tr>
        <td class="text-muted small">${ts}</td>
        <td class="font-monospace small">${item.resource_name || '—'}</td>
        <td class="small">${item.operation || '—'}</td>
        <td class="small">${item.workflow_name || '—'}</td>
        <td>${outcome}</td>
        <td class="font-monospace small text-muted">${item.conductor_workflow_id ? item.conductor_workflow_id.substring(0,16) + '...' : '—'}</td>
      </tr>`;
    }).join('');
  } catch (e) {
    console.error('History load error', e);
  }
}

loadHistory();

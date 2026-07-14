'use strict';

const DOB_BUCKET_BADGE = {
  HIGH: 'badge-error',
  MEDIUM: 'badge-silent',
  REVIEW: 'badge-unknown',
};

// ── Status + analyze ────────────────────────────────────────────────────────

async function dobLoadStatus() {
  try {
    const r = await fetch('/api/dob-repair/status');
    const s = await r.json();
    document.getElementById('dob-analyze-status').textContent = s.analyzed
      ? 'Last analyzed: ' + new Date(s.analyzed_at).toLocaleString() + ' — source: ' + s.source
      : 'No analysis has been run yet.';
    document.getElementById('dob-reload-configured-btn').classList.toggle('d-none', !s.configured_input_path);
    document.getElementById('dob-fetch-sql-btn').classList.toggle('d-none', !s.sql_configured);
  } catch {
    // Status is informational only — fail quietly, upload still works.
  }
}

async function dobAnalyze(useConfiguredPath) {
  const fileInput = document.getElementById('dob-csv-file');
  const thresholdInput = document.getElementById('dob-threshold');
  const btn = document.getElementById('dob-analyze-btn');
  const statusEl = document.getElementById('dob-analyze-status');

  const file = fileInput.files ? fileInput.files[0] : null;
  if (!file && !useConfiguredPath) {
    alert('Choose a CSV file first');
    return;
  }

  const form = new FormData();
  if (file && !useConfiguredPath) form.append('csv_file', file);
  form.append('threshold', thresholdInput.value || '6');

  btn.disabled = true;
  statusEl.textContent = 'Analyzing...';

  try {
    const r = await fetch('/api/dob-repair/analyze', { method: 'POST', body: form });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || 'Analyze failed');

    statusEl.textContent = 'Analyzed ' + data.summary.total_records + ' records — ' +
      data.summary.high + ' HIGH, ' + data.summary.medium + ' MEDIUM, ' + data.summary.review + ' REVIEW';
    await dobLoadStatus();
    await dobLoadCandidates();
  } catch (err) {
    alert('Analyze failed: ' + err.message);
    statusEl.textContent = 'Analyze failed: ' + err.message;
  } finally {
    btn.disabled = false;
  }
}

async function dobAnalyzeSql() {
  const thresholdInput = document.getElementById('dob-threshold');
  const btn = document.getElementById('dob-fetch-sql-btn');
  const statusEl = document.getElementById('dob-analyze-status');

  btn.disabled = true;
  statusEl.textContent = 'Running configured SQL query...';

  try {
    const r = await fetch('/api/dob-repair/analyze/sql', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ threshold: parseInt(thresholdInput.value || '6', 10) }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error + (data.setup ? ' — ' + data.setup : ''));

    statusEl.textContent = 'Analyzed ' + data.summary.total_records + ' records via SQL — ' +
      data.summary.high + ' HIGH, ' + data.summary.medium + ' MEDIUM, ' + data.summary.review + ' REVIEW';
    await dobLoadStatus();
    await dobLoadCandidates();
  } catch (err) {
    alert('SQL fetch failed: ' + err.message);
    statusEl.textContent = 'SQL fetch failed: ' + err.message;
  } finally {
    btn.disabled = false;
  }
}

// ── Candidates + rendering ──────────────────────────────────────────────────

async function dobLoadCandidates() {
  const r = await fetch('/api/dob-repair/candidates');
  if (!r.ok) return; // 404 NOT_ANALYZED before the first analysis — leave placeholder
  const data = await r.json();
  dobRenderSummary(data.summary);
  dobRenderCandidates(data.candidates || []);
  dobRenderElevated(data.elevated_risk || []);
  dobRenderUnparseable(data.unparseable_dob || []);
}

function dobRenderSummary(s) {
  if (!s) return;
  document.getElementById('tile-total').textContent = s.total_records;
  document.getElementById('tile-high').textContent = s.high;
  document.getElementById('tile-medium').textContent = s.medium;
  document.getElementById('tile-review').textContent = s.review;
  document.getElementById('tile-elevated').textContent = s.elevated_risk;
  document.getElementById('tile-unparseable').textContent = s.unparseable_dob;
}

function dobDecisionBadge(decision) {
  if (!decision) return '<span class="badge badge-unknown">undecided</span>';
  const cls = decision.action === 'accept' ? 'badge-active' : decision.action === 'reject' ? 'badge-error' : 'badge-silent';
  return '<span class="badge ' + cls + '">' + decision.action + '</span>' +
    '<div class="text-muted" style="font-size:.72rem">' + (decision.reviewer || '') + '</div>';
}

function dobRenderCandidates(candidates) {
  const tbody = document.getElementById('dob-candidates-tbody');
  if (!candidates.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="text-muted text-center py-3">No candidates found in this export.</td></tr>';
    return;
  }

  tbody.innerHTML = candidates.map(function (c) {
    const badgeCls = DOB_BUCKET_BADGE[c.bucket] || 'badge-unknown';
    const earlierChecked = c.suggested_true_dob && c.suggested_true_dob === c.earlier_dob ? 'checked' : '';
    const laterChecked = c.suggested_true_dob && c.suggested_true_dob === c.later_dob ? 'checked' : '';
    const radioName = 'dob-true-' + c.candidate_id;

    return '<tr data-candidate-id="' + c.candidate_id + '">' +
      '<td><span class="badge ' + badgeCls + '">' + c.bucket + '</span></td>' +
      '<td>' + c.name + '</td>' +
      '<td>' + c.earlier_dob + ' <span class="text-muted small">(' + c.earlier_origin + ')</span></td>' +
      '<td>' + c.later_dob + ' <span class="text-muted small">(' + c.later_origin + ')</span></td>' +
      '<td>' + c.identity_score + '</td>' +
      '<td class="small" style="max-width:280px">' + c.rationale + '</td>' +
      '<td style="min-width:220px">' +
        '<div class="mb-1">' + dobDecisionBadge(c.decision) + '</div>' +
        '<div class="d-flex flex-column gap-1 small">' +
          '<label><input type="radio" name="' + radioName + '" class="dob-true-radio" value="' + c.earlier_dob + '" ' + earlierChecked + '/> Earlier is true</label>' +
          '<label><input type="radio" name="' + radioName + '" class="dob-true-radio" value="' + c.later_dob + '" ' + laterChecked + '/> Later is true</label>' +
        '</div>' +
        '<div class="d-flex gap-1 mt-1">' +
          '<button class="btn btn-sm btn-doane dob-decide-btn" data-action="accept">Accept</button>' +
          '<button class="btn btn-sm btn-outline-secondary dob-decide-btn" data-action="reject">Reject</button>' +
          '<button class="btn btn-sm btn-outline-secondary dob-decide-btn" data-action="defer">Defer</button>' +
        '</div>' +
      '</td>' +
    '</tr>';
  }).join('');
}

function dobRenderElevated(list) {
  document.getElementById('dob-elevated-count').textContent = '(' + list.length + ')';
  const tbody = document.getElementById('dob-elevated-tbody');
  if (!list.length) {
    tbody.innerHTML = '<tr><td colspan="4" class="text-muted text-center py-2">None.</td></tr>';
    return;
  }
  tbody.innerHTML = list.map(function (r) {
    return '<tr><td>' + r.person_id + '</td><td>' + r.name + '</td><td>' + r.dob + '</td><td>' + r.state + '</td></tr>';
  }).join('');
}

function dobRenderUnparseable(list) {
  const card = document.getElementById('dob-unparseable-card');
  const tbody = document.getElementById('dob-unparseable-tbody');
  if (!list.length) {
    card.classList.add('d-none');
    return;
  }
  card.classList.remove('d-none');
  tbody.innerHTML = list.map(function (r) {
    return '<tr><td>' + r.person_id + '</td><td>' + r.name + '</td><td>' + r.raw_birth_date + '</td></tr>';
  }).join('');
}

// ── Decisions ────────────────────────────────────────────────────────────────

async function dobDecide(row, action) {
  const candidateId = row.dataset.candidateId;
  let trueDob = '';

  if (action === 'accept') {
    const checked = row.querySelector('.dob-true-radio:checked');
    if (!checked) {
      alert('Pick which date is true before accepting');
      return;
    }
    trueDob = checked.value;
    if (!confirm('Accept correction for candidate ' + candidateId + '?\n\n' +
        'This marks a specific person record as needing its DOB corrected to ' + trueDob +
        ' and adds it to the corrections export. It does not write to Colleague by itself.')) return;
  }

  try {
    const r = await fetch('/api/dob-repair/decision', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ candidate_id: candidateId, action: action, true_dob: trueDob, reviewer: 'console' }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.error || 'Decision failed');
    await dobLoadCandidates();
  } catch (err) {
    alert('Decision failed: ' + err.message);
  }
}

// ── Export ───────────────────────────────────────────────────────────────────

async function dobExportCorrections() {
  window.location.href = '/api/dob-repair/export/corrections';
}

// ── Wiring ───────────────────────────────────────────────────────────────────

document.getElementById('dob-analyze-btn').addEventListener('click', function () { dobAnalyze(false); });
document.getElementById('dob-reload-configured-btn').addEventListener('click', function () { dobAnalyze(true); });
document.getElementById('dob-fetch-sql-btn').addEventListener('click', dobAnalyzeSql);
document.getElementById('dob-export-btn').addEventListener('click', dobExportCorrections);

document.getElementById('dob-elevated-toggle-btn').addEventListener('click', function () {
  const content = document.getElementById('dob-elevated-content');
  const nowHidden = content.classList.toggle('d-none');
  this.textContent = nowHidden ? 'Show' : 'Hide';
});

document.getElementById('dob-candidates-tbody').addEventListener('click', function (e) {
  const btn = e.target.closest('.dob-decide-btn');
  if (!btn) return;
  const row = btn.closest('tr[data-candidate-id]');
  if (!row) return;
  dobDecide(row, btn.dataset.action);
});

dobLoadStatus();
dobLoadCandidates();

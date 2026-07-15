"""Tests for /api/dob-repair endpoints — PD0002124 DOB shift detector.

The shared `app`/`client` fixtures are session-scoped (tests/conftest.py), so
unlike conductor-tools' equivalent suite this file cannot rely on a fresh
per-test database — an autouse fixture clears both DobDecision rows and the
routes module's in-memory _STATE dict before/after every test.
"""
import io
import os

import pytest

from app.database import db, DobDecision
from app.routes import dob_repair as dob_repair_routes

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "dob_sample_persons.csv")

# Deterministic candidate ids from the fixture (sorted person_id pair).
SMITH_HIGH = "1001__1002"     # HIGH: IE 4/2 vs authoritative 4/3
KING_HIGH = "3001__3002"      # HIGH: year-boundary shift
LEE_REVIEW = "5001__5002"     # REVIEW: IE record is the later date


@pytest.fixture(autouse=True)
def _reset_dob_state(app):
    def _clear():
        dob_repair_routes._STATE.update({
            "result": None, "by_id": {}, "source": None, "analyzed_at": None,
            "identity_threshold": dob_repair_routes.detector.IDENTITY_THRESHOLD,
        })
        with app.app_context():
            DobDecision.query.delete()
            db.session.commit()

    _clear()
    yield
    _clear()


def _upload(client, filename="dob_sample_persons.csv"):
    with open(FIXTURE, "rb") as fh:
        data = fh.read()
    return client.post(
        "/api/dob-repair/analyze",
        data={"csv_file": (io.BytesIO(data), filename)},
        content_type="multipart/form-data",
    )


# ── Status ────────────────────────────────────────────────────────────────────

def test_status_before_analysis(client):
    resp = client.get("/api/dob-repair/status")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["analyzed"] is False
    assert data["configured_input_path"] is False


def test_candidates_before_analysis_returns_404(client):
    resp = client.get("/api/dob-repair/candidates")
    assert resp.status_code == 404


# ── Analyze ───────────────────────────────────────────────────────────────────

def test_no_file_and_no_configured_path_returns_400(client):
    resp = client.post("/api/dob-repair/analyze", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_upload_analyzes_and_returns_summary(client):
    resp = _upload(client)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["source"] == "dob_sample_persons.csv"
    summary = data["summary"]
    assert summary["high"] == 2
    assert summary["medium"] == 1
    assert summary["review"] == 1
    assert summary["elevated_risk"] == 3


def test_status_reflects_analysis(client):
    _upload(client)
    resp = client.get("/api/dob-repair/status")
    data = resp.get_json()
    assert data["analyzed"] is True
    assert data["source"] == "dob_sample_persons.csv"


# ── Candidates ────────────────────────────────────────────────────────────────

def test_candidates_joined_with_no_decisions(client):
    _upload(client)
    resp = client.get("/api/dob-repair/candidates")
    assert resp.status_code == 200
    data = resp.get_json()
    ids = {c["candidate_id"] for c in data["candidates"]}
    assert SMITH_HIGH in ids
    assert KING_HIGH in ids
    assert LEE_REVIEW in ids
    smith = next(c for c in data["candidates"] if c["candidate_id"] == SMITH_HIGH)
    assert smith["bucket"] == "HIGH"
    assert smith["decision"] is None


def test_elevated_risk_and_summary_present(client):
    _upload(client)
    resp = client.get("/api/dob-repair/candidates")
    data = resp.get_json()
    elevated_ids = {r["person_id"] for r in data["elevated_risk"]}
    assert {"4001", "8001", "7001"}.issubset(elevated_ids)
    assert data["summary"]["total_records"] == 14


# ── Decision ──────────────────────────────────────────────────────────────────

def test_unknown_candidate_returns_404(client):
    _upload(client)
    resp = client.post("/api/dob-repair/decision", json={
        "candidate_id": "nope__nope", "action": "reject",
    })
    assert resp.status_code == 404


def test_invalid_action_returns_400(client):
    _upload(client)
    resp = client.post("/api/dob-repair/decision", json={
        "candidate_id": SMITH_HIGH, "action": "approve",
    })
    assert resp.status_code == 400


def test_accept_without_true_dob_returns_400(client):
    _upload(client)
    resp = client.post("/api/dob-repair/decision", json={
        "candidate_id": SMITH_HIGH, "action": "accept",
    })
    assert resp.status_code == 400


def test_accept_high_candidate_flags_ie_record_for_correction(client):
    _upload(client)
    resp = client.post("/api/dob-repair/decision", json={
        "candidate_id": SMITH_HIGH, "action": "accept",
        "true_dob": "1980-04-03", "reviewer": "reviewer@doane.edu",
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["corrected_person_id"] == "1001"
    assert data["corrected_from"] == "1980-04-02"
    assert data["corrected_to"] == "1980-04-03"


def test_accept_true_dob_must_match_a_side(client):
    _upload(client)
    resp = client.post("/api/dob-repair/decision", json={
        "candidate_id": SMITH_HIGH, "action": "accept",
        "true_dob": "1999-01-01",
    })
    assert resp.status_code == 400


def test_reject_records_no_correction(client):
    _upload(client)
    resp = client.post("/api/dob-repair/decision", json={
        "candidate_id": LEE_REVIEW, "action": "reject", "reviewer": "r",
    })
    assert resp.status_code == 200
    assert resp.get_json()["corrected_person_id"] is None


def test_decision_emits_audit_event_without_dob_values(client, app):
    # The audit entry must record that a decision happened (candidate_id,
    # action, reviewer) without duplicating the DOB values themselves into a
    # second, less-access-controlled table.
    from app.database import AuditEntry
    _upload(client)
    client.post("/api/dob-repair/decision", json={
        "candidate_id": LEE_REVIEW, "action": "reject", "reviewer": "pytest-reviewer",
    })
    with app.app_context():
        entry = AuditEntry.query.filter_by(
            action="update", resource_type="dob_decision", resource_id=LEE_REVIEW,
        ).order_by(AuditEntry.occurred_at.desc()).first()
    assert entry is not None
    assert entry.detail["decision_action"] == "reject"
    assert entry.detail["reviewer"] == "pytest-reviewer"
    detail_values = set(entry.detail.values())
    assert "1999-01-01" not in detail_values  # no DOB value leaked into audit detail


def test_decision_persists_across_candidate_reload(client):
    _upload(client)
    client.post("/api/dob-repair/decision", json={
        "candidate_id": SMITH_HIGH, "action": "accept", "true_dob": "1980-04-03",
    })
    resp = client.get("/api/dob-repair/candidates")
    smith = next(c for c in resp.get_json()["candidates"] if c["candidate_id"] == SMITH_HIGH)
    assert smith["decision"]["action"] == "accept"
    assert smith["decision"]["corrected_person_id"] == "1001"


def test_decision_upserts_on_resubmit(client):
    _upload(client)
    client.post("/api/dob-repair/decision", json={
        "candidate_id": LEE_REVIEW, "action": "defer",
    })
    resp = client.post("/api/dob-repair/decision", json={
        "candidate_id": LEE_REVIEW, "action": "reject", "note": "typo, not the bug",
    })
    assert resp.status_code == 200
    assert resp.get_json()["action"] == "reject"


# ── Export corrections ───────────────────────────────────────────────────────

def test_export_is_csv(client):
    _upload(client)
    resp = client.get("/api/dob-repair/export/corrections")
    assert resp.status_code == 200
    assert "text/csv" in resp.content_type
    assert "attachment" in resp.headers.get("Content-Disposition", "")


def test_export_contains_only_accepted_with_correction(client):
    _upload(client)
    client.post("/api/dob-repair/decision", json={
        "candidate_id": SMITH_HIGH, "action": "accept", "true_dob": "1980-04-03",
    })
    client.post("/api/dob-repair/decision", json={
        "candidate_id": KING_HIGH, "action": "defer",
    })
    client.post("/api/dob-repair/decision", json={
        "candidate_id": LEE_REVIEW, "action": "reject",
    })

    resp = client.get("/api/dob-repair/export/corrections")
    csv_text = resp.data.decode("utf-8")
    assert "person_id,current_dob,corrected_dob" in csv_text
    assert "1001,1980-04-02,1980-04-03" in csv_text
    assert "3001" not in csv_text
    assert "5001" not in csv_text
    assert "5002" not in csv_text


def test_export_empty_before_any_acceptance(client):
    _upload(client)
    resp = client.get("/api/dob-repair/export/corrections")
    csv_text = resp.data.decode("utf-8")
    lines = [l for l in csv_text.strip().splitlines() if l]
    assert len(lines) == 1  # header only


# ── SQL fetch source (round 2) ───────────────────────────────────────────────

def _make_record(**kw):
    from app import dob_detector as detector
    base = dict(
        person_id="x", last_name="", first_name="", middle_name="",
        birth_date=None, addr_line1="", city="", state="", zip="",
        email="", phone="", origin="", created_date="",
    )
    base.update(kw)
    return detector.Record(**base)


def test_status_sql_not_configured_by_default(client):
    resp = client.get("/api/dob-repair/status")
    assert resp.get_json()["sql_configured"] is False


def test_status_sql_configured(client, monkeypatch):
    monkeypatch.setattr(dob_repair_routes.dob_sql_source, "is_configured", lambda: True)
    resp = client.get("/api/dob-repair/status")
    assert resp.get_json()["sql_configured"] is True


def test_analyze_sql_not_configured_returns_503(client, monkeypatch):
    monkeypatch.setattr(dob_repair_routes.dob_sql_source, "is_configured", lambda: False)
    resp = client.post("/api/dob-repair/analyze/sql", json={})
    assert resp.status_code == 503


def test_analyze_sql_successful_fetch(client, monkeypatch):
    from datetime import date

    monkeypatch.setattr(dob_repair_routes.dob_sql_source, "is_configured", lambda: True)
    monkeypatch.setattr(dob_repair_routes.dob_sql_source, "sql_file_path", lambda: "/srv/dob_query.sql")

    records = [
        _make_record(person_id="1001", last_name="Smith", first_name="John",
                     birth_date=date(1980, 4, 2), zip="23220", addr_line1="120 Elm St",
                     email="j@x.com", phone="8045551212", origin="INSTANT_ENROLL"),
        _make_record(person_id="1002", last_name="Smith", first_name="John",
                     birth_date=date(1980, 4, 3), zip="23220", addr_line1="120 Elm St",
                     email="j@x.com", phone="8045551212", origin="APP_IMPORT"),
    ]
    monkeypatch.setattr(dob_repair_routes.dob_sql_source, "fetch_records", lambda: records)

    resp = client.post("/api/dob-repair/analyze/sql", json={"threshold": 6})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["source"] == "sql:/srv/dob_query.sql"
    assert data["summary"]["high"] == 1

    cand_resp = client.get("/api/dob-repair/candidates")
    ids = {c["candidate_id"] for c in cand_resp.get_json()["candidates"]}
    assert SMITH_HIGH in ids


def test_analyze_sql_unsafe_query_returns_400(client, monkeypatch):
    monkeypatch.setattr(dob_repair_routes.dob_sql_source, "is_configured", lambda: True)

    def _raise_unsafe():
        raise ValueError("DOB_RECONCILE_SQL_FILE contains a disallowed keyword")

    monkeypatch.setattr(dob_repair_routes.dob_sql_source, "fetch_records", lambda: _raise_unsafe())
    resp = client.post("/api/dob-repair/analyze/sql", json={})
    assert resp.status_code == 400


def test_analyze_sql_missing_pyodbc_returns_503(client, monkeypatch):
    monkeypatch.setattr(dob_repair_routes.dob_sql_source, "is_configured", lambda: True)

    def _raise_runtime_error():
        raise RuntimeError("pyodbc is not installed")

    monkeypatch.setattr(dob_repair_routes.dob_sql_source, "fetch_records", lambda: _raise_runtime_error())
    resp = client.post("/api/dob-repair/analyze/sql", json={})
    assert resp.status_code == 503


def test_analyze_sql_db_connectivity_error_returns_502(client, monkeypatch):
    monkeypatch.setattr(dob_repair_routes.dob_sql_source, "is_configured", lambda: True)

    def _raise_db_error():
        raise Exception("could not connect to sqlserver.doane.edu")

    monkeypatch.setattr(dob_repair_routes.dob_sql_source, "fetch_records", lambda: _raise_db_error())
    resp = client.post("/api/dob-repair/analyze/sql", json={})
    assert resp.status_code == 502

"""Unit tests for app/auth.py — check_key, api_auth_required, _auth_enabled."""
import hmac
import pytest
from unittest.mock import patch


# ── check_key ─────────────────────────────────────────────────────────────────

def test_check_key_correct(app):
    original = app.config.get("CONSOLE_KEY", "")
    try:
        app.config["CONSOLE_KEY"] = "my-secret"
        with app.app_context():
            from app.auth import check_key
            assert check_key("my-secret") is True
    finally:
        app.config["CONSOLE_KEY"] = original


def test_check_key_wrong(app):
    original = app.config.get("CONSOLE_KEY", "")
    try:
        app.config["CONSOLE_KEY"] = "my-secret"
        with app.app_context():
            from app.auth import check_key
            assert check_key("wrong") is False
    finally:
        app.config["CONSOLE_KEY"] = original


def test_check_key_empty_key_allows_all(app):
    """No CONSOLE_KEY configured → every submitted value passes."""
    original = app.config.get("CONSOLE_KEY", "")
    try:
        app.config["CONSOLE_KEY"] = ""
        with app.app_context():
            from app.auth import check_key
            assert check_key("anything") is True
            assert check_key("") is True
    finally:
        app.config["CONSOLE_KEY"] = original


def test_check_key_trims_whitespace(app):
    original = app.config.get("CONSOLE_KEY", "")
    try:
        app.config["CONSOLE_KEY"] = "secret"
        with app.app_context():
            from app.auth import check_key
            assert check_key("  secret  ") is True
    finally:
        app.config["CONSOLE_KEY"] = original


def test_check_key_uses_hmac_compare_digest(app):
    """Confirm hmac.compare_digest is used (timing-safe comparison)."""
    original = app.config.get("CONSOLE_KEY", "")
    try:
        app.config["CONSOLE_KEY"] = "key"
        with app.app_context():
            from app import auth as auth_module
            with patch.object(hmac, "compare_digest", wraps=hmac.compare_digest) as mock_cd:
                auth_module.check_key("key")
                mock_cd.assert_called_once()
    finally:
        app.config["CONSOLE_KEY"] = original


# ── api_auth_required ─────────────────────────────────────────────────────────

def test_api_auth_required_open_when_no_key(app):
    """With no CONSOLE_KEY, API routes are accessible with no credentials."""
    original = app.config.get("CONSOLE_KEY", "")
    try:
        app.config["CONSOLE_KEY"] = ""
        r = app.test_client().get("/api/health/")
        assert r.status_code == 200
    finally:
        app.config["CONSOLE_KEY"] = original


def test_api_auth_required_header_key(app):
    """X-Console-Key header with correct value grants access."""
    original = app.config.get("CONSOLE_KEY", "")
    try:
        app.config["CONSOLE_KEY"] = "hdr-secret"
        r = app.test_client().get("/api/health/",
                                  headers={"X-Console-Key": "hdr-secret"})
        assert r.status_code == 200
    finally:
        app.config["CONSOLE_KEY"] = original


def test_api_auth_required_wrong_header_key(app):
    original = app.config.get("CONSOLE_KEY", "")
    try:
        app.config["CONSOLE_KEY"] = "hdr-secret"
        r = app.test_client().get("/api/health/",
                                  headers={"X-Console-Key": "wrong"})
        assert r.status_code == 401
        assert r.get_json()["error"] == "Unauthorized"
    finally:
        app.config["CONSOLE_KEY"] = original


def test_api_auth_required_no_header_no_session(app):
    original = app.config.get("CONSOLE_KEY", "")
    try:
        app.config["CONSOLE_KEY"] = "hdr-secret"
        r = app.test_client().get("/api/health/")
        assert r.status_code == 401
    finally:
        app.config["CONSOLE_KEY"] = original


def test_api_auth_required_session_grants_access(app):
    original = app.config.get("CONSOLE_KEY", "")
    try:
        app.config["CONSOLE_KEY"] = "sess-secret"
        client = app.test_client()
        client.post("/login", data={"key": "sess-secret", "next": "/"})
        r = client.get("/api/health/")
        assert r.status_code == 200
    finally:
        app.config["CONSOLE_KEY"] = original

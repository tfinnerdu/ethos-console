"""Simple key-based auth gate for the dev console.

Set CONSOLE_KEY in .env to any shared passphrase.  Leave it blank to allow
unrestricted access (safe for localhost-only dev).  To tie into your Conductor
instance with a single credential, set CONSOLE_KEY to the same value as
CONDUCTOR_API_KEY — one key, one team login.
"""
import hmac
from functools import wraps
from flask import session, redirect, url_for, request, current_app


def is_authenticated() -> bool:
    return bool(session.get("authenticated"))


def check_key(submitted: str) -> bool:
    expected = current_app.config.get("CONSOLE_KEY", "")
    if not expected:
        return True  # no key set → open access (dev mode)
    return hmac.compare_digest(submitted.strip(), expected.strip())


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not _auth_enabled():
            return f(*args, **kwargs)
        if not is_authenticated():
            return redirect(url_for("auth.login", next=request.path))
        return f(*args, **kwargs)
    return decorated


def api_auth_required(f):
    """For API routes: check session or X-Console-Key header."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not _auth_enabled():
            return f(*args, **kwargs)
        if is_authenticated():
            return f(*args, **kwargs)
        header_key = request.headers.get("X-Console-Key", "")
        if header_key and check_key(header_key):
            return f(*args, **kwargs)
        from flask import jsonify
        return jsonify({"error": "Unauthorized"}), 401
    return decorated


def _auth_enabled() -> bool:
    return bool(current_app.config.get("CONSOLE_KEY", ""))

"""Single-credential login gate, with optional Entra ID (Azure AD) SSO.

A shared username/password (sourced from a Kubernetes secret via
AUTH_USERNAME / AUTH_PASSWORD, delivered to the container as plaintext env
vars) gates every route except health checks, static assets, and the login
page itself. There is no per-user identity in this path — one credential for
the whole app. See docs/auth-gate-guide.md for the general pattern.

When ENTRA_TENANT_ID/ENTRA_CLIENT_ID/ENTRA_CLIENT_SECRET/ENTRA_REDIRECT_URI
are all set (see app/auth_entra.py), the gate auto-redirects unauthenticated
browser requests straight to Microsoft's sign-in page instead of the local
form — giving real per-user identity via login()'s username argument. The
local form stays reachable directly at /login as a fallback (Entra outage,
or before the app registration/admin consent is finished) rather than being
retired outright; see docs/auth-gate-guide.md's "Migrating to SSO" section
for the fuller swap-out if you want to retire AUTH_USERNAME/AUTH_PASSWORD
entirely later.

Fail-closed: if NEITHER local credentials (safely, i.e. also a non-default
SECRET_KEY) NOR Entra are configured, every non-exempt route is blocked
rather than silently left open. This replaces the previous CONSOLE_KEY-based
gate, which was fail-open (unrestricted access whenever CONSOLE_KEY was
unset) and only applied via per-route decorators — 8 of the app's ~13 API
blueprints, including ones that execute arbitrary GraphQL and raw
UniData/Colleague commands, had zero decorator coverage. This module's
before_request hook protects everything by default instead.
"""
import hmac
import time

from flask import current_app, g, jsonify, redirect, request, session, url_for

DEFAULT_SECRET_KEY = "dev-secret-change-in-prod"

# Paths reachable with no session at all. /api/health/live backs the k8s
# liveness AND readiness probes (k8s/deployment.yaml) and is pinned by
# test_contracts.py::test_health_live_always_200 to always return 200 — it
# must never depend on auth being configured, or a misconfigured secret
# turns into a crash-looping pod instead of an app that simply refuses to
# serve the UI. /api/health/ (bare) and /api/health/token stay gated.
# /login/entra and /api/v1/auth/callback must work with no session at all
# too — the callback is where Microsoft sends the browser back
# mid-handshake, before anyone's signed in yet. The callback path starts
# with /api/ but is exempt before the gate's is_api classification even
# runs, so it's never mistaken for a gated JSON API route.
_EXEMPT_PATHS = {"/login", "/logout", "/login/entra", "/api/v1/auth/callback", "/api/health/live"}
_EXEMPT_PREFIXES = ("/static/",)

_FAILED_LOGIN_DELAY_SECONDS = 1.0


def is_configured() -> bool:
    return bool(
        current_app.config.get("AUTH_USERNAME", "").strip()
        and current_app.config.get("AUTH_PASSWORD", "")
    )


def secret_key_is_default() -> bool:
    return current_app.config.get("SECRET_KEY") == DEFAULT_SECRET_KEY


def is_safely_configured() -> bool:
    """Configured AND signed with a real (non-default) SECRET_KEY.

    A configured username/password is worthless if sessions are signed with
    the publicly-known default key — anyone could forge a valid
    'authenticated' cookie without ever calling verify_credentials().
    """
    return is_configured() and not secret_key_is_default()


def is_entra_configured() -> bool:
    return bool(
        current_app.config.get("ENTRA_TENANT_ID", "").strip()
        and current_app.config.get("ENTRA_CLIENT_ID", "").strip()
        and current_app.config.get("ENTRA_CLIENT_SECRET", "")
        and current_app.config.get("ENTRA_REDIRECT_URI", "").strip()
    )


def verify_credentials(username: str, password: str) -> bool:
    expected_user = current_app.config.get("AUTH_USERNAME", "")
    expected_pass = current_app.config.get("AUTH_PASSWORD", "")
    user_ok = hmac.compare_digest((username or "").encode(), expected_user.encode())
    pass_ok = hmac.compare_digest((password or "").encode(), expected_pass.encode())
    return user_ok and pass_ok


def login(username: str) -> None:
    session.clear()
    session["authenticated"] = True
    session["username"] = username
    session.permanent = True


def logout() -> None:
    session.clear()


def is_authenticated() -> bool:
    return bool(session.get("authenticated"))


def record_failed_login(username: str) -> None:
    current_app.logger.warning(
        "login failed: username=%r remote_addr=%s", username, request.remote_addr
    )
    time.sleep(_FAILED_LOGIN_DELAY_SECONDS)


def safe_next_path(value: str) -> str:
    """Only allow a same-origin relative path as a post-login redirect target.

    Rejects anything with a scheme (http://...) or a protocol-relative
    '//host/...' — both of which some browsers would treat as an external
    redirect — to avoid an open-redirect via a crafted `next=`.

    Checked against a backslash-normalized copy first: browsers treat '\'
    as '/' when resolving http(s) URLs (the WHATWG URL Standard's "special
    scheme" backslash normalization), so '/\\evil.com', '\\/evil.com', and
    '\\\\evil.com' all resolve to the same protocol-relative '//evil.com' a
    browser would follow off-site, even though none of them literally
    starts with "//".
    """
    if not value:
        return "/"
    normalized = value.replace("\\", "/")
    if not normalized.startswith("/") or normalized.startswith("//"):
        return "/"
    return normalized


def _is_exempt(path: str) -> bool:
    if path in _EXEMPT_PATHS:
        return True
    return path.startswith(_EXEMPT_PREFIXES)


def register_auth_gate(app) -> None:
    @app.before_request
    def _auth_gate():
        # The existing test suite runs with TESTING=True and never
        # configures AUTH_*; a fail-closed gate would otherwise block every
        # test in every test_*_api.py file. The dedicated auth tests
        # (tests/test_auth.py) build a non-TESTING app instance specifically
        # to exercise this hook for real.
        if current_app.testing:
            return None

        path = request.path
        if _is_exempt(path):
            return None

        is_api = path.startswith("/api/")
        entra_ready = is_entra_configured()

        # SECRET_KEY signs the Flask session cookie used by BOTH auth
        # paths (local login and Entra) — a default/known key lets anyone
        # forge a valid "authenticated" session regardless of which
        # mechanism is otherwise configured. This check is therefore
        # unconditional: previously it was only folded into
        # is_safely_configured() (which only gates the *local credentials*
        # path), so a deployment with Entra configured but SECRET_KEY still
        # at its default sailed straight past the fail-closed check below —
        # a session forged with the well-known default key would pass
        # is_authenticated() without Entra ever being contacted.
        if secret_key_is_default() or (not is_configured() and not entra_ready):
            if is_api:
                return jsonify({
                    "error": "Authentication is not configured on this deployment",
                }), 503
            return redirect(url_for("auth.login_page"))

        if not is_authenticated():
            if is_api:
                return jsonify({"error": "Authentication required"}), 401
            if entra_ready:
                return redirect(url_for("auth.login_entra", next=path))
            return redirect(url_for("auth.login_page", next=path))

        # Real per-user identity (Entra) or the shared username (local
        # login) — either way, this is what app/audit.py's write_event()
        # attributes the action to instead of falling back to "anonymous".
        g.current_user = session.get("username")

        return None

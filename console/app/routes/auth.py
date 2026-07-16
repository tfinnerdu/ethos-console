"""Auth routes — /login, /logout, and the Entra ID (Azure AD) SSO pair.

See app/auth.py for the gate itself (the before_request hook that redirects
here, to /login or /login/entra depending on what's configured). This
blueprint handles the login form, session clearing, and — when Entra is
configured — the sign-in-initiation and callback routes.
"""
import hmac
import secrets

from flask import Blueprint, current_app, redirect, render_template, request, session, url_for

from app import auth
from app.auth_entra import SCOPES, build_msal_app

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login_page():
    entra_configured = auth.is_entra_configured()

    if not auth.is_safely_configured():
        if entra_configured:
            # Local credentials aren't set up, but Entra is — go straight
            # there rather than show a form that's guaranteed to fail.
            return redirect(url_for("auth.login_entra", next=request.args.get("next", "/")))
        current_app.logger.warning(
            "login attempted but auth is not safely configured "
            "(AUTH_USERNAME/AUTH_PASSWORD unset, or SECRET_KEY is still the "
            "default) — see docs/auth-gate-guide.md"
        )
        return render_template("login.html", not_configured=True), 503

    if auth.is_authenticated():
        return redirect(auth.safe_next_path(request.args.get("next", "/")))

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        next_path = auth.safe_next_path(request.form.get("next", "/"))

        if auth.verify_credentials(username, password):
            auth.login(username)
            current_app.logger.info("login succeeded: username=%r", username)
            return redirect(next_path)

        auth.record_failed_login(username)
        return render_template(
            "login.html",
            error="Invalid username or password.",
            next=next_path,
            entra_configured=entra_configured,
        ), 401

    return render_template(
        "login.html",
        next=auth.safe_next_path(request.args.get("next", "/")),
        entra_configured=entra_configured,
    )


@auth_bp.get("/logout")
def logout_view():
    auth.logout()
    return redirect(url_for("auth.login_page"))


# ── Entra ID (Azure AD) SSO ───────────────────────────────────────────────────
# See docs/auth-gate-guide.md's "Migrating to SSO" section and
# app/auth_entra.py. Both routes must work with no session at all — the
# callback is where Microsoft sends the browser back mid-handshake, before
# anyone's signed in yet — so neither is gated (see app/auth.py's
# _EXEMPT_PATHS).

def _build_entra_app():
    cfg = current_app.config
    return build_msal_app(cfg["ENTRA_TENANT_ID"], cfg["ENTRA_CLIENT_ID"], cfg["ENTRA_CLIENT_SECRET"])


@auth_bp.get("/login/entra")
def login_entra():
    if not auth.is_entra_configured():
        return redirect(url_for("auth.login_page"))

    next_path = auth.safe_next_path(request.args.get("next", "/"))

    # state = CSRF binding, nonce = OIDC replay binding. Both generated here,
    # stashed pre-login, and checked again in the callback below.
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    session["entra_state"] = state
    session["entra_nonce"] = nonce
    session["entra_next"] = next_path

    try:
        msal_app = _build_entra_app()
        auth_url = msal_app.get_authorization_request_url(
            SCOPES, state=state, nonce=nonce, redirect_uri=current_app.config["ENTRA_REDIRECT_URI"],
        )
    except Exception as exc:
        # A tenant-discovery network hiccup shouldn't 500 the whole route.
        current_app.logger.warning("Entra sign-in initiation failed: %s", exc)
        return redirect(url_for("auth.login_page"))
    return redirect(auth_url)


@auth_bp.get("/auth/callback")
def auth_callback():
    next_path = auth.safe_next_path(session.pop("entra_next", "/"))
    expected_state = session.pop("entra_state", None)
    expected_nonce = session.pop("entra_nonce", None)

    if request.args.get("error"):
        # User cancelled, or an IdP-side error — never a 500.
        current_app.logger.warning(
            "Entra callback returned an error: %s",
            request.args.get("error_description", request.args.get("error")),
        )
        return redirect(url_for("auth.login_page"))

    state = request.args.get("state", "")
    if not expected_state or not hmac.compare_digest(state, expected_state):
        current_app.logger.warning("Entra callback state mismatch — possible CSRF, refusing")
        return redirect(url_for("auth.login_page"))

    code = request.args.get("code", "")
    if not code:
        return redirect(url_for("auth.login_page"))

    try:
        msal_app = _build_entra_app()
        result = msal_app.acquire_token_by_authorization_code(
            code, scopes=SCOPES, redirect_uri=current_app.config["ENTRA_REDIRECT_URI"],
        )
    except Exception as exc:
        current_app.logger.warning("Entra token exchange failed: %s", exc)
        return redirect(url_for("auth.login_page"))

    if "error" in result:
        current_app.logger.warning(
            "Entra token exchange returned an error: %s",
            result.get("error_description", result.get("error")),
        )
        return redirect(url_for("auth.login_page"))

    claims = result.get("id_token_claims") or {}
    # MSAL already verified signature/exp/aud/iss for real. Nonce binding
    # (replay protection) is left to the caller — that's this check.
    if not expected_nonce or not hmac.compare_digest(str(claims.get("nonce", "")), expected_nonce):
        current_app.logger.warning("Entra callback nonce mismatch — possible replay, refusing")
        return redirect(url_for("auth.login_page"))

    # Fallback chain: not every tenant configuration populates email on the
    # ID token.
    email = claims.get("email") or claims.get("preferred_username") or claims.get("upn")
    if not email:
        current_app.logger.warning("Entra callback had no usable identity claim")
        return redirect(url_for("auth.login_page"))

    auth.login(email)
    current_app.logger.info("Entra login succeeded: user=%r", email)
    return redirect(next_path)

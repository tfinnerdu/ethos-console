"""Auth routes — /login, /logout

See app/auth.py for the gate itself (the before_request hook that redirects
here). This blueprint only handles the login form and clearing the session.
"""
from flask import Blueprint, current_app, redirect, render_template, request, url_for

from app import auth

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login_page():
    if not auth.is_safely_configured():
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
        ), 401

    return render_template("login.html", next=auth.safe_next_path(request.args.get("next", "/")))


@auth_bp.get("/logout")
def logout_view():
    auth.logout()
    return redirect(url_for("auth.login_page"))

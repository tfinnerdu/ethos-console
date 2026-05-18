from flask import Blueprint, render_template, request, redirect, url_for, session, current_app
from app.auth import check_key

auth_bp = Blueprint("auth", __name__)


@auth_bp.get("/login")
def login():
    if session.get("authenticated"):
        return redirect(url_for("main.index"))
    next_url = request.args.get("next", "/")
    return render_template("login.html", next_url=next_url, auth_enabled=bool(current_app.config.get("CONSOLE_KEY")))


@auth_bp.post("/login")
def login_post():
    key = request.form.get("key", "")
    next_url = request.form.get("next", "/")
    if check_key(key):
        session.permanent = True
        session["authenticated"] = True
        return redirect(next_url or "/")
    return render_template("login.html", next_url=next_url, error="Invalid access key.",
                           auth_enabled=bool(current_app.config.get("CONSOLE_KEY")))


@auth_bp.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))

from flask import Blueprint, render_template, current_app

main_bp = Blueprint("main", __name__)


@main_bp.get("/")
def index():
    return render_template("bus_monitor.html", active_tab="bus")


@main_bp.get("/replay")
def replay():
    conductor_url = current_app.config.get("CONDUCTOR_URL", "")
    return render_template("replay.html", active_tab="replay", conductor_url=conductor_url)


@main_bp.get("/graphql")
def graphql_ui():
    return render_template("graphql.html", active_tab="graphql")


@main_bp.get("/resources")
def resources():
    return render_template("resources.html", active_tab="resources")


@main_bp.get("/mnemonics")
def mnemonics():
    return render_template("mnemonics.html", active_tab="mnemonics")


@main_bp.get("/health")
def health_ui():
    return render_template("health.html", active_tab="health")


@main_bp.get("/errors")
def errors_ui():
    return render_template("errors.html", active_tab="health")

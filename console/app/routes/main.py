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


@main_bp.get("/dob-repair")
def dob_repair():
    return render_template("dob_repair.html", active_tab="dob_repair")


@main_bp.get("/health")
def health_ui():
    return render_template("health.html", active_tab="health")


@main_bp.get("/errors")
def errors_ui():
    return render_template("errors.html", active_tab="health")


@main_bp.get("/schema-browser")
def schema_browser():
    return render_template("schema_browser.html", active_tab="schema_browser")


@main_bp.get("/field-diff")
def field_diff():
    unidata_configured = bool(current_app.config.get("UNIDATA_HOST"))
    return render_template("field_diff.html", active_tab="field_diff",
                           unidata_configured=unidata_configured)


@main_bp.get("/colleague-query")
def colleague_query():
    unidata_configured = bool(current_app.config.get("UNIDATA_HOST"))
    return render_template("colleague_query.html", active_tab="colleague_query",
                           unidata_configured=unidata_configured)


@main_bp.get("/colleague-api")
def colleague_api():
    colleague_configured = bool(current_app.config.get("COLLEAGUE_WEB_API_URL"))
    return render_template("colleague_api.html", active_tab="colleague_api",
                           colleague_configured=colleague_configured)


@main_bp.get("/cn-monitor")
def cn_monitor():
    ethos_configured = bool(current_app.config.get("ETHOS_ENVIRONMENTS"))
    return render_template("cn_monitor.html", active_tab="cn_monitor",
                           ethos_configured=ethos_configured)

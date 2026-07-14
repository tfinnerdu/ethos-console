import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")
    CONDUCTOR_API_KEY = os.environ.get("CONDUCTOR_API_KEY", "")
    CONDUCTOR_URL = os.environ.get("CONDUCTOR_URL", "")
    UNIDATA_CONN_STR = os.environ.get("UNIDATA_CONN_STR", "")
    COLLEAGUE_WEB_API_URL = os.environ.get("COLLEAGUE_WEB_API_URL", "")
    COLLEAGUE_WEB_API_USER = os.environ.get("COLLEAGUE_WEB_API_USER", "")
    COLLEAGUE_WEB_API_PASS = os.environ.get("COLLEAGUE_WEB_API_PASS", "")
    UNIDATA_HOST = os.environ.get("UNIDATA_HOST", "")
    UNIDATA_PORT = int(os.environ.get("UNIDATA_PORT", "31438"))
    UNIDATA_USER = os.environ.get("UNIDATA_USER", "")
    UNIDATA_PASSWORD = os.environ.get("UNIDATA_PASSWORD", "")
    UNIDATA_ACCOUNT = os.environ.get("UNIDATA_ACCOUNT", "")

    # Single-credential login gate (app/auth.py) — gates every route except
    # health checks. FAIL-CLOSED: if either is unset, every non-health route
    # is blocked (503), not silently ungated. See docs/auth-gate-guide.md.
    AUTH_USERNAME = os.environ.get("AUTH_USERNAME", "")
    AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "")
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("AUTH_COOKIE_SECURE", "true") in (
        "1", "true", "True", "yes",
    )
    PERMANENT_SESSION_LIFETIME = timedelta(
        hours=float(os.environ.get("AUTH_SESSION_LIFETIME_HOURS", "8"))
    )

    # DOB Repair — optional SQL Server fetch source (app/dob_sql_source.py),
    # alternative to CSV upload. Leave unset to keep DOB Repair CSV-only.
    DOB_RECONCILE_INPUT_CSV = os.environ.get("DOB_RECONCILE_INPUT_CSV", "")

    BUS_POLL_INTERVAL = int(os.environ.get("BUS_POLL_INTERVAL", "2"))
    SILENCE_THRESHOLD_MINUTES = int(os.environ.get("SILENCE_THRESHOLD_MINUTES", "30"))
    ALERT_WEBHOOK_URL = os.environ.get("ALERT_WEBHOOK_URL", "")
    ALERT_ERROR_THRESHOLD = int(os.environ.get("ALERT_ERROR_THRESHOLD", "10"))
    CONSOLE_MOCK_MODE = os.environ.get("CONSOLE_MOCK_MODE", "").strip().lower() in (
        "1", "true", "yes", "on",
    )
    # An environment is required — one entry feeds the whole console. Define a
    # second / third one to make the nav-bar dropdown appear; pick the active
    # one at startup with DEFAULT_ENV.
    #
    # ETHOS_ENV_n_GRAPHQL_KEY is optional. Use it when an environment's bus key
    # doesn't have GraphQL scope and you need a separately-scoped key just for
    # introspection / GraphQL execution. Falls back to ETHOS_ENV_n_KEY.
    ETHOS_ENVIRONMENTS = [
        {
            "name": os.environ.get(f"ETHOS_ENV_{i}_NAME", ""),
            "url": os.environ.get(f"ETHOS_ENV_{i}_URL", "https://integrate.elluciancloud.com"),
            "key": os.environ.get(f"ETHOS_ENV_{i}_KEY", ""),
            "graphql_key": os.environ.get(f"ETHOS_ENV_{i}_GRAPHQL_KEY", ""),
        }
        for i in range(1, 6)
        if os.environ.get(f"ETHOS_ENV_{i}_NAME") and os.environ.get(f"ETHOS_ENV_{i}_KEY")
    ]
    DEFAULT_ENV = os.environ.get("DEFAULT_ENV", "").strip()

    _db_url = os.environ.get("DATABASE_URL", "")
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url or "sqlite:///ethos_console.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class DevelopmentConfig(Config):
    DEBUG = True
    ENV = "development"

class ProductionConfig(Config):
    DEBUG = False
    ENV = "production"

config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}

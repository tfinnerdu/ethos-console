import os
from datetime import timedelta


def _normalize_database_url(raw: str) -> str:
    """Accept either a full DB URI or a bare filesystem path for DATABASE_URL.

    A bare path (no "://" — e.g. "sf_mission_control.db", "/data/foo.db",
    "C:\\data\\foo.db") matches the SF Mission Control sibling app's simpler
    DATABASE_PATH convention. Building the sqlite:/// URI here instead of
    asking the operator to hand-count "how many slashes mean absolute" (4 on
    Linux, 3 on Windows — a real footgun that broke a real deployment) means
    they can just write a normal OS path. A full URI (postgresql://...,
    sqlite://... already correctly slashed) passes through unchanged, aside
    from the postgres:// -> postgresql:// SQLAlchemy dialect rename.
    """
    raw = raw.strip()
    if not raw:
        return ""
    if "://" not in raw:
        return "sqlite:///" + raw.replace("\\", "/")
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql://", 1)
    return raw


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")
    CONDUCTOR_API_KEY = os.environ.get("CONDUCTOR_API_KEY", "")
    CONDUCTOR_URL = os.environ.get("CONDUCTOR_URL", "")
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

    # Entra ID (Azure AD) SSO — optional. When all four are set, the login
    # gate auto-redirects unauthenticated browser requests straight to
    # Microsoft's sign-in page instead of the local username/password form
    # (which stays reachable directly at /login as a fallback — e.g. if
    # Entra has an outage, or during initial setup before the app
    # registration/admin consent is done). See docs/auth-gate-guide.md's
    # "Migrating to SSO" section and app/auth_entra.py.
    ENTRA_TENANT_ID = os.environ.get("ENTRA_TENANT_ID", "")
    ENTRA_CLIENT_ID = os.environ.get("ENTRA_CLIENT_ID", "")
    ENTRA_CLIENT_SECRET = os.environ.get("ENTRA_CLIENT_SECRET", "")
    ENTRA_REDIRECT_URI = os.environ.get("ENTRA_REDIRECT_URI", "")

    # DOB Repair — optional SQL Server fetch source (app/dob_sql_source.py),
    # alternative to CSV upload. Leave unset to keep DOB Repair CSV-only.
    DOB_RECONCILE_INPUT_CSV = os.environ.get("DOB_RECONCILE_INPUT_CSV", "")

    # DOB Repair — institution-specific origin/operator codes that mark a
    # PERSON record as Instant-Enroll-created, in ADDITION to the generic
    # defaults in app/dob_detector.py's IE_ORIGIN_VALUES (e.g. a numeric web-
    # registration operator ID, or "GUEST"/"WEBCASHIER"-style process names —
    # whatever your Colleague PERSON_ADD_OPERATOR-equivalent column actually
    # contains). Comma-separated. See the "Origin-code portability" note in
    # app/dob_detector.py's module docstring for why these live in config,
    # not in that shared module.
    DOB_RECONCILE_IE_ORIGIN_CODES = os.environ.get("DOB_RECONCILE_IE_ORIGIN_CODES", "")

    # DoaneEdgeGate — the DOB-shift prevention reverse proxy in front of the
    # Colleague Web API (see DoaneEdgeGate/README.md). Base URL only, e.g.
    # "http://localhost:5199" or "https://edge-gate.internal.doane.edu"; the
    # console appends /health itself. Leave unset to show the Health tab tile
    # as "not configured" rather than treating an unrelated deployment as down.
    EDGE_GATE_URL = os.environ.get("EDGE_GATE_URL", "")

    BUS_POLL_INTERVAL = int(os.environ.get("BUS_POLL_INTERVAL", "2"))
    SILENCE_THRESHOLD_MINUTES = int(os.environ.get("SILENCE_THRESHOLD_MINUTES", "30"))
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

    SQLALCHEMY_DATABASE_URI = _normalize_database_url(os.environ.get("DATABASE_URL", "")) or "sqlite:///ethos_console.db"
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

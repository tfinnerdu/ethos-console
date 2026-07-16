import os
import logging
from flask import Flask
from .database import db, seed_mnemonics, seed_saved_queries
from .ethos_client import EthosClient
from .colleague_api_client import ColleagueApiClient
from .conductor_client import ConductorClient
from .unidata_client import UnidataClient
from .cn_repository import CnRepository
from .bus_monitor import BusMonitor
from .health_monitor import EthosHealthMonitor
from .edge_gate_client import EdgeGateClient
from config import config


def create_app(config_name: str | None = None, overrides: dict | None = None) -> Flask:
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(
        __name__,
        template_folder="templates",
        static_folder=os.path.join(os.path.dirname(__file__), "..", "static"),
        static_url_path="/static",
    )
    app.config.from_object(config.get(config_name, config["default"]))
    if overrides:
        app.config.update(overrides)

    # Fail-closed on the DB, mirroring the auth gate's own fail-closed posture
    # (app/auth.py): a production run with no DATABASE_URL silently falls back
    # to a local SQLite file (config.py) that does not survive a pod restart —
    # every replay/audit/mnemonic/DOB-decision record would vanish on the next
    # redeploy with no error, no warning. k8s/secret-template.yaml already
    # documents "DATABASE_URL MUST be PostgreSQL in k8s" as a comment; this
    # turns that comment into an actual boot-time check.
    if app.config.get("ENV") == "production" and app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
        raise RuntimeError(
            "Refusing to start with ENV=production and no DATABASE_URL (or a "
            "sqlite:// DATABASE_URL). SQLite does not survive a pod restart — "
            "every replay/audit/mnemonic/DOB-decision record would be silently "
            "lost on the next redeploy. Set DATABASE_URL to a Postgres "
            "connection string (see k8s/secret-template.yaml)."
        )

    logging.basicConfig(
        level=logging.DEBUG if app.config["DEBUG"] else logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    )

    db.init_app(app)

    # Single-credential login gate (see app/auth.py) — fail-closed if
    # AUTH_USERNAME/AUTH_PASSWORD aren't configured, or SECRET_KEY is still
    # the default. Registered before blueprint imports so it governs every
    # route registered below.
    from app.auth import register_auth_gate
    register_auth_gate(app)

    with app.app_context():
        db.create_all()
        seed_mnemonics(app)
        seed_saved_queries(app)

    mock_mode = bool(app.config.get("CONSOLE_MOCK_MODE"))
    app.extensions["mock_mode"] = mock_mode

    # Pick the active Ethos environment at startup:
    #   1. DEFAULT_ENV — case-insensitive match against an ETHOS_ENV_n NAME.
    #   2. First configured ETHOS_ENV_n.
    #   3. None — every Ethos-dependent tab will surface its 503 setup state.
    # The selected env's credentials feed the EthosClient from the first
    # request onward, so the dropdown selection and the in-flight key always
    # match. No top-level ETHOS_API_KEY fallback — one config pattern, one
    # source of truth.
    envs = app.config.get("ETHOS_ENVIRONMENTS", [])
    default_name = (app.config.get("DEFAULT_ENV") or "").strip()
    active_env = None
    if default_name and envs:
        active_env = next(
            (e for e in envs if e["name"].lower() == default_name.lower()),
            None,
        )
        if not active_env:
            logging.getLogger(__name__).warning(
                "DEFAULT_ENV=%r does not match any configured ETHOS_ENV_n "
                "(have %s); falling back to %r.",
                default_name,
                [e["name"] for e in envs],
                envs[0]["name"],
            )
    if not active_env and envs:
        active_env = envs[0]
    if not active_env and not mock_mode:
        logging.getLogger(__name__).warning(
            "No ETHOS_ENV_n configured. Add ETHOS_ENV_1_NAME / _URL / _KEY to "
            ".env to enable Ethos-dependent tabs."
        )
    elif active_env:
        # Always emit this so an operator can verify the dropdown matches
        # what's actually in flight — answers "why am I not on the env I
        # set DEFAULT_ENV to?" without grepping config.
        logging.getLogger(__name__).info(
            "Active Ethos environment: %r (url=%s, dedicated graphql key=%s)",
            active_env["name"],
            active_env["url"],
            "yes" if active_env.get("graphql_key") else "no",
        )

    if mock_mode:
        logging.getLogger(__name__).warning(
            "CONSOLE_MOCK_MODE is ON — every upstream call returns fixture data. "
            "No real credentials are used."
        )
        from .mocks import (
            MockEthosClient, MockColleagueApiClient,
            MockConductorClient, MockUnidataClient, MockCnRepository,
            MockEdgeGateClient,
        )
        ethos = MockEthosClient()
        colleague_api = MockColleagueApiClient()
        conductor = MockConductorClient()
        unidata = MockUnidataClient()
        cn_repository = MockCnRepository()
        edge_gate = MockEdgeGateClient()
    else:
        ethos = EthosClient(
            api_key=active_env["key"] if active_env else "",
            base_url=active_env["url"] if active_env else "https://integrate.elluciancloud.com",
        )
        colleague_api = ColleagueApiClient(
            base_url=app.config.get("COLLEAGUE_WEB_API_URL", ""),
            username=app.config.get("COLLEAGUE_WEB_API_USER", ""),
            password=app.config.get("COLLEAGUE_WEB_API_PASS", ""),
        )
        conductor = ConductorClient(
            base_url=app.config.get("CONDUCTOR_URL", ""),
            api_key=app.config.get("CONDUCTOR_API_KEY", ""),
        )
        unidata = UnidataClient(
            host=app.config.get("UNIDATA_HOST", ""),
            port=app.config.get("UNIDATA_PORT", 31438),
            user=app.config.get("UNIDATA_USER", ""),
            password=app.config.get("UNIDATA_PASSWORD", ""),
            account=app.config.get("UNIDATA_ACCOUNT", ""),
        )
        cn_repository = CnRepository(colleague_api_client=colleague_api)
        edge_gate = EdgeGateClient(base_url=app.config.get("EDGE_GATE_URL", ""))

    monitor = BusMonitor(ethos)
    health_monitor = EthosHealthMonitor(ethos)

    # Bus Monitor defaults to stopped — it does not auto-start polling Ethos
    # on boot. Start it explicitly from the Bus Monitor tab (POST
    # /api/bus/start), so an idle console doesn't spam Ethos with /consume
    # requests every BUS_POLL_INTERVAL seconds when nobody is watching.

    app.extensions["ethos_client"] = ethos
    app.extensions["colleague_api_client"] = colleague_api
    app.extensions["conductor_client"] = conductor
    app.extensions["unidata_client"] = unidata
    app.extensions["cn_repository"] = cn_repository
    app.extensions["bus_monitor"] = monitor
    app.extensions["health_monitor"] = health_monitor
    app.extensions["edge_gate_client"] = edge_gate

    app.extensions["current_env_name"] = active_env["name"] if active_env else ""

    # Mock-mode signal #3 (UI badge + health key are the other two): every
    # API response carries X-Mock-Mode so an operator / consumer can never
    # mistake mock output for live data.
    if mock_mode:
        @app.after_request
        def _add_mock_header(response):
            response.headers["X-Mock-Mode"] = "true"
            return response

    @app.context_processor
    def _inject_env():
        current = app.extensions.get("current_env_name", "")
        environments = app.config.get("ETHOS_ENVIRONMENTS", [])
        if mock_mode:
            # Every feature is exercisable in mock mode — clear all "off" badges.
            configured_features = {
                k: True for k in
                ("ethos", "conductor", "unidata", "colleague_api", "edge_gate")
            }
        else:
            configured_features = {
                "ethos":         bool(app.config.get("ETHOS_ENVIRONMENTS")),
                "conductor":     bool(app.config.get("CONDUCTOR_URL")),
                "unidata":       bool(app.config.get("UNIDATA_HOST")),
                "colleague_api": bool(app.config.get("COLLEAGUE_WEB_API_URL")),
                "edge_gate":     bool(app.config.get("EDGE_GATE_URL")),
            }
        return {
            "ethos_environments": environments,
            "current_ethos_env": current,
            "configured_features": configured_features,
            "mock_mode": mock_mode,
        }

    from .routes.auth import auth_bp
    from .routes.main import main_bp
    from .routes.bus import bus_bp
    from .routes.health import health_bp
    from .routes.replay import replay_bp
    from .routes.mnemonics import mnemonics_bp
    from .routes.resources import resources_bp
    from .routes.graphql_routes import graphql_bp
    from .routes.errors import errors_bp
    from .routes.schema_browser import schema_browser_bp
    from .routes.phase3 import phase3_bp
    from .routes.cn_monitor import cn_bp
    from .routes.env import env_bp
    from .routes.colleague_api import colleague_api_bp
    from .routes.dob_repair import dob_repair_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(bus_bp, url_prefix="/api/bus")
    app.register_blueprint(health_bp, url_prefix="/api/health")
    app.register_blueprint(replay_bp, url_prefix="/api/replay")
    app.register_blueprint(mnemonics_bp, url_prefix="/api/mnemonics")
    app.register_blueprint(dob_repair_bp, url_prefix="/api/dob-repair")
    app.register_blueprint(resources_bp, url_prefix="/api/resources")
    app.register_blueprint(graphql_bp, url_prefix="/api/graphql-console")
    app.register_blueprint(errors_bp, url_prefix="/api/errors")
    app.register_blueprint(schema_browser_bp, url_prefix="/api/schema-browser")
    app.register_blueprint(phase3_bp, url_prefix="/api/phase3")
    app.register_blueprint(cn_bp, url_prefix="/api/cn")
    app.register_blueprint(env_bp, url_prefix="/api/env")
    app.register_blueprint(colleague_api_bp, url_prefix="/api/colleague")

    return app


def get_ethos(app: Flask) -> EthosClient:
    return app.extensions["ethos_client"]


def get_monitor(app: Flask) -> BusMonitor:
    return app.extensions["bus_monitor"]


def get_health_monitor(app: Flask) -> EthosHealthMonitor:
    return app.extensions["health_monitor"]


def get_conductor(app: Flask) -> ConductorClient:
    return app.extensions["conductor_client"]


def get_unidata(app: Flask) -> UnidataClient:
    return app.extensions["unidata_client"]


def get_edge_gate(app: Flask) -> EdgeGateClient:
    return app.extensions["edge_gate_client"]

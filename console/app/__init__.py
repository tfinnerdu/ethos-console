import os
import logging
from flask import Flask
from .database import db, seed_mnemonics, seed_saved_queries
from .ethos_client import EthosClient
from .cn_client import CnmClient
from .colleague_api_client import ColleagueApiClient
from .conductor_client import ConductorClient
from .unidata_client import UnidataClient
from .bus_monitor import BusMonitor
from .health_monitor import EthosHealthMonitor
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

    logging.basicConfig(
        level=logging.DEBUG if app.config["DEBUG"] else logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    )

    db.init_app(app)

    with app.app_context():
        db.create_all()
        seed_mnemonics(app)
        seed_saved_queries(app)

    mock_mode = bool(app.config.get("CONSOLE_MOCK_MODE"))
    app.extensions["mock_mode"] = mock_mode

    if mock_mode:
        logging.getLogger(__name__).warning(
            "CONSOLE_MOCK_MODE is ON — every upstream call returns fixture data. "
            "No real credentials are used."
        )
        from .mocks import (
            MockEthosClient, MockCnmClient, MockColleagueApiClient,
            MockConductorClient, MockUnidataClient,
        )
        ethos = MockEthosClient()
        cnm = MockCnmClient()
        colleague_api = MockColleagueApiClient()
        conductor = MockConductorClient()
        unidata = MockUnidataClient()
    else:
        ethos = EthosClient(
            api_key=app.config["ETHOS_API_KEY"],
            base_url=app.config["ETHOS_BASE_URL"],
        )
        cnm = CnmClient(
            base_url=app.config.get("CNM_BASE_URL", ""),
            api_key=app.config.get("CNM_API_KEY", ""),
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

    monitor = BusMonitor(ethos)
    health_monitor = EthosHealthMonitor(ethos)

    if ethos.is_configured() and not app.config.get("TESTING"):
        monitor.start(poll_interval=app.config["BUS_POLL_INTERVAL"], app=app)

    app.extensions["ethos_client"] = ethos
    app.extensions["cnm_client"] = cnm
    app.extensions["colleague_api_client"] = colleague_api
    app.extensions["conductor_client"] = conductor
    app.extensions["unidata_client"] = unidata
    app.extensions["bus_monitor"] = monitor
    app.extensions["health_monitor"] = health_monitor

    envs = app.config.get("ETHOS_ENVIRONMENTS", [])
    app.extensions["current_env_name"] = envs[0]["name"] if envs else ""

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
                ("ethos", "conductor", "cnm", "unidata", "colleague_api", "alerting")
            }
        else:
            configured_features = {
                "ethos":         bool(app.config.get("ETHOS_API_KEY")),
                "conductor":     bool(app.config.get("CONDUCTOR_URL")),
                "cnm":           bool(app.config.get("CNM_BASE_URL")),
                "unidata":       bool(app.config.get("UNIDATA_HOST")),
                "colleague_api": bool(app.config.get("COLLEAGUE_WEB_API_URL")),
                "alerting":      bool(app.config.get("ALERT_WEBHOOK_URL")),
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

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(bus_bp, url_prefix="/api/bus")
    app.register_blueprint(health_bp, url_prefix="/api/health")
    app.register_blueprint(replay_bp, url_prefix="/api/replay")
    app.register_blueprint(mnemonics_bp, url_prefix="/api/mnemonics")
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

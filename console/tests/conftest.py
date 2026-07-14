"""Pytest fixtures for the Ethos Dev Console test suite."""
import pytest
from unittest.mock import MagicMock, patch
from app import create_app
from app.database import db as _db


@pytest.fixture(scope="session")
def app():
    """App configured for testing: in-memory SQLite, no Ethos polling."""
    with patch("app.ethos_client.EthosClient.is_configured", return_value=False):
        flask_app = create_app("development")

    flask_app.config.update(
        TESTING=True,
        # DEBUG=False matters beyond Flask's own behavior: the first current_app.logger
        # access on a DEBUG=True app makes Flask set the "app"-named logger to DEBUG
        # (flask.logging.create_logger). uopy (imported by unidata_client.py) globally
        # reclasses every not-yet-created logger to its own UOLogger the moment it's
        # imported, and UOLogger.debug() has a real arg-count bug once DEBUG-enabled —
        # so leaving this True risks poisoning app.health_monitor's logger for the rest
        # of the suite the first time any route logs via current_app.logger.
        DEBUG=False,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        ETHOS_ENVIRONMENTS=[],
        WTF_CSRF_ENABLED=False,
    )

    with flask_app.app_context():
        _db.create_all()
        yield flask_app
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def mock_ethos(app):
    """Replace app.extensions['ethos_client'] with a MagicMock for one test."""
    original = app.extensions.get("ethos_client")
    mock = MagicMock()
    mock.is_configured.return_value = True
    mock.token_status = {"valid": True, "expires_in_minutes": 45}
    mock.get_queue_depth.return_value = 0
    mock.get_available_resources.return_value = [
        {"name": "persons", "latestVersion": "16"},
        {"name": "courses", "latestVersion": "16"},
    ]
    mock.get_cn_available_resources.return_value = [{"resourceName": "persons"}]
    mock.graphql.return_value = {"data": {}}
    app.extensions["ethos_client"] = mock
    yield mock
    app.extensions["ethos_client"] = original

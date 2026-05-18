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
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        ETHOS_API_KEY="",
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
    """Return the EthosClient stored in app.extensions, replaced with a MagicMock."""
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
    return mock

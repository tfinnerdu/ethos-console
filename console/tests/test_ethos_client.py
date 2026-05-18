"""Unit tests for EthosClient — all HTTP calls mocked."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import pytest
from app.ethos_client import EthosClient


@pytest.fixture()
def client():
    return EthosClient(api_key="test-api-key",
                       base_url="https://integrate.elluciancloud.com")


@pytest.fixture()
def unconfigured():
    return EthosClient(api_key="")


# ── is_configured ─────────────────────────────────────────────────────────────

def test_is_configured_true_when_key_set(client):
    assert client.is_configured() is True


def test_is_configured_false_when_no_key(unconfigured):
    assert unconfigured.is_configured() is False


# ── token_status ──────────────────────────────────────────────────────────────

def test_token_status_invalid_when_no_token(client):
    status = client.token_status
    assert status["valid"] is False
    assert status["expires_in_minutes"] == 0


def test_token_status_valid_with_fresh_token(client):
    client._token = "tok"
    client._token_expiry = datetime.now(timezone.utc) + timedelta(minutes=45)
    status = client.token_status
    assert status["valid"] is True
    assert status["expires_in_minutes"] == 45


def test_token_status_invalid_when_expired(client):
    client._token = "tok"
    client._token_expiry = datetime.now(timezone.utc) - timedelta(minutes=1)
    status = client.token_status
    assert status["valid"] is False
    assert status["expires_in_minutes"] == 0


# ── get_token + caching ───────────────────────────────────────────────────────

def test_get_token_fetches_from_api(client):
    mock_resp = MagicMock()
    mock_resp.text = '"jwt-token-value"'
    mock_resp.raise_for_status = MagicMock()

    with patch("app.ethos_client.requests.post", return_value=mock_resp) as mock_post:
        token = client.get_token()

    assert token == "jwt-token-value"
    mock_post.assert_called_once()


def test_get_token_uses_cache_on_second_call(client):
    mock_resp = MagicMock()
    mock_resp.text = '"cached-token"'
    mock_resp.raise_for_status = MagicMock()

    with patch("app.ethos_client.requests.post", return_value=mock_resp) as mock_post:
        client.get_token()
        client.get_token()

    mock_post.assert_called_once()


def test_get_token_refetches_when_expired(client):
    client._token = "old-token"
    client._token_expiry = datetime.now(timezone.utc) - timedelta(minutes=1)

    mock_resp = MagicMock()
    mock_resp.text = '"new-token"'
    mock_resp.raise_for_status = MagicMock()

    with patch("app.ethos_client.requests.post", return_value=mock_resp):
        token = client.get_token()

    assert token == "new-token"


def test_get_token_sets_55_min_expiry(client):
    mock_resp = MagicMock()
    mock_resp.text = '"tok"'
    mock_resp.raise_for_status = MagicMock()

    before = datetime.now(timezone.utc)
    with patch("app.ethos_client.requests.post", return_value=mock_resp):
        client.get_token()
    after = datetime.now(timezone.utc)

    remaining = (client._token_expiry - after).total_seconds() / 60
    # Should be close to 55 minutes
    assert 54 < remaining <= 55


# ── get_headers ───────────────────────────────────────────────────────────────

def test_get_headers_contains_bearer(client):
    client._token = "my-token"
    client._token_expiry = datetime.now(timezone.utc) + timedelta(minutes=30)
    headers = client.get_headers()
    assert headers["Authorization"] == "Bearer my-token"


def test_get_headers_default_accept_json(client):
    client._token = "tok"
    client._token_expiry = datetime.now(timezone.utc) + timedelta(minutes=30)
    headers = client.get_headers()
    assert headers["Accept"] == "application/json"


def test_get_headers_custom_accept(client):
    client._token = "tok"
    client._token_expiry = datetime.now(timezone.utc) + timedelta(minutes=30)
    headers = client.get_headers(accept="application/vnd.hedtech.integration.v16+json")
    assert "v16" in headers["Accept"]


# ── get_resource ──────────────────────────────────────────────────────────────

def test_get_resource_calls_correct_url(client):
    client._token = "tok"
    client._token_expiry = datetime.now(timezone.utc) + timedelta(minutes=30)

    mock_resp = MagicMock()
    mock_resp.json.return_value = [{"id": "abc"}]
    mock_resp.raise_for_status = MagicMock()

    with patch("app.ethos_client.requests.get", return_value=mock_resp) as mock_get:
        result = client.get_resource("persons")

    call_url = mock_get.call_args[0][0]
    assert call_url.endswith("/api/persons")
    assert result == [{"id": "abc"}]


def test_get_resource_uses_versioned_accept_when_version_given(client):
    client._token = "tok"
    client._token_expiry = datetime.now(timezone.utc) + timedelta(minutes=30)

    mock_resp = MagicMock()
    mock_resp.json.return_value = []
    mock_resp.raise_for_status = MagicMock()

    with patch("app.ethos_client.requests.get", return_value=mock_resp) as mock_get:
        client.get_resource("persons", version="16")

    headers_used = mock_get.call_args[1]["headers"]
    assert "v16" in headers_used["Accept"]


# ── graphql ───────────────────────────────────────────────────────────────────

def test_graphql_posts_to_graphql_endpoint(client):
    client._token = "tok"
    client._token_expiry = datetime.now(timezone.utc) + timedelta(minutes=30)

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": {}}
    mock_resp.raise_for_status = MagicMock()

    with patch("app.ethos_client.requests.post", return_value=mock_resp) as mock_post:
        client.graphql("{ persons16 { edges { node { id } } } }")

    call_url = mock_post.call_args[0][0]
    assert call_url.endswith("/graphql")


def test_graphql_includes_variables_when_provided(client):
    client._token = "tok"
    client._token_expiry = datetime.now(timezone.utc) + timedelta(minutes=30)

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": {}}
    mock_resp.raise_for_status = MagicMock()

    with patch("app.ethos_client.requests.post", return_value=mock_resp) as mock_post:
        client.graphql("query Q($id: String!) { }", variables={"id": "123"})

    body = mock_post.call_args[1]["json"]
    assert body["variables"] == {"id": "123"}


def test_graphql_omits_variables_when_none(client):
    client._token = "tok"
    client._token_expiry = datetime.now(timezone.utc) + timedelta(minutes=30)

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": {}}
    mock_resp.raise_for_status = MagicMock()

    with patch("app.ethos_client.requests.post", return_value=mock_resp) as mock_post:
        client.graphql("{ persons16 { edges { node { id } } } }")

    body = mock_post.call_args[1]["json"]
    assert "variables" not in body


# ── consume_messages ──────────────────────────────────────────────────────────

def test_consume_messages_passes_limit(client):
    client._token = "tok"
    client._token_expiry = datetime.now(timezone.utc) + timedelta(minutes=30)

    mock_resp = MagicMock()
    mock_resp.json.return_value = []
    mock_resp.raise_for_status = MagicMock()

    with patch("app.ethos_client.requests.get", return_value=mock_resp) as mock_get:
        client.consume_messages(limit=10)

    params = mock_get.call_args[1]["params"]
    assert params["limit"] == 10


def test_consume_messages_passes_last_processed_id(client):
    client._token = "tok"
    client._token_expiry = datetime.now(timezone.utc) + timedelta(minutes=30)

    mock_resp = MagicMock()
    mock_resp.json.return_value = []
    mock_resp.raise_for_status = MagicMock()

    with patch("app.ethos_client.requests.get", return_value=mock_resp) as mock_get:
        client.consume_messages(limit=5, last_processed_id=99)

    params = mock_get.call_args[1]["params"]
    assert params["lastProcessedID"] == 99


def test_consume_messages_returns_empty_list_for_null_response(client):
    client._token = "tok"
    client._token_expiry = datetime.now(timezone.utc) + timedelta(minutes=30)

    mock_resp = MagicMock()
    mock_resp.json.return_value = None
    mock_resp.raise_for_status = MagicMock()

    with patch("app.ethos_client.requests.get", return_value=mock_resp):
        result = client.consume_messages()

    assert result == []


# ── get_queue_depth ───────────────────────────────────────────────────────────

def test_get_queue_depth_integer_response(client):
    client._token = "tok"
    client._token_expiry = datetime.now(timezone.utc) + timedelta(minutes=30)

    mock_resp = MagicMock()
    mock_resp.json.return_value = 42
    mock_resp.raise_for_status = MagicMock()

    with patch("app.ethos_client.requests.get", return_value=mock_resp):
        depth = client.get_queue_depth()

    assert depth == 42


def test_get_queue_depth_dict_response(client):
    client._token = "tok"
    client._token_expiry = datetime.now(timezone.utc) + timedelta(minutes=30)

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"count": 17}
    mock_resp.raise_for_status = MagicMock()

    with patch("app.ethos_client.requests.get", return_value=mock_resp):
        depth = client.get_queue_depth()

    assert depth == 17

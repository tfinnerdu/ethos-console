"""Unit tests for EdgeGateClient — all HTTP calls mocked."""
from unittest.mock import MagicMock, patch

import pytest

from app.edge_gate_client import EdgeGateClient


@pytest.fixture()
def gate():
    return EdgeGateClient(base_url="http://gate.local:5199")


@pytest.fixture()
def unconfigured():
    return EdgeGateClient(base_url="")


def test_is_configured_true_when_url_set(gate):
    assert gate.is_configured() is True


def test_is_configured_false_when_no_url(unconfigured):
    assert unconfigured.is_configured() is False


def test_check_health_unconfigured_never_calls_out(unconfigured):
    with patch("app.edge_gate_client.requests.get") as mock_get:
        result = unconfigured.check_health()
    mock_get.assert_not_called()
    assert result == {"configured": False, "reachable": False, "status": "unconfigured"}


def test_check_health_reachable_parses_gate_shape(gate):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "status": "ok", "service": "DoaneEdgeGate", "version": "1.0.0", "uptime_seconds": 42,
    }
    with patch("app.edge_gate_client.requests.get", return_value=mock_resp) as mock_get:
        result = gate.check_health()

    mock_get.assert_called_once_with("http://gate.local:5199/health", timeout=5, allow_redirects=False)
    assert result == {
        "configured": True,
        "reachable": True,
        "status": "ok",
        "service": "DoaneEdgeGate",
        "version": "1.0.0",
        "uptime_seconds": 42,
    }


def test_check_health_strips_trailing_slash_from_base_url():
    gate = EdgeGateClient(base_url="http://gate.local:5199/")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "ok"}
    with patch("app.edge_gate_client.requests.get", return_value=mock_resp) as mock_get:
        gate.check_health()
    mock_get.assert_called_once_with("http://gate.local:5199/health", timeout=5, allow_redirects=False)


def test_check_health_unreachable_on_connection_error(gate):
    with patch("app.edge_gate_client.requests.get", side_effect=ConnectionError("refused")):
        result = gate.check_health()
    assert result["configured"] is True
    assert result["reachable"] is False
    assert result["status"] == "unreachable"
    assert "refused" in result["error"]


def test_check_health_unreachable_on_http_error(gate):
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("502 Bad Gateway")
    with patch("app.edge_gate_client.requests.get", return_value=mock_resp):
        result = gate.check_health()
    assert result["reachable"] is False
    assert result["status"] == "unreachable"


@pytest.mark.parametrize("non_dict_body", [None, [], "ok", 42, True])
def test_check_health_degrades_on_non_dict_json_body(gate, non_dict_body):
    # A 200 with valid-but-non-object JSON (e.g. a captive portal or proxy
    # error page that happens to emit valid JSON) must degrade to
    # "unreachable", not raise AttributeError out of check_health().
    mock_resp = MagicMock()
    mock_resp.json.return_value = non_dict_body
    with patch("app.edge_gate_client.requests.get", return_value=mock_resp):
        result = gate.check_health()
    assert result["configured"] is True
    assert result["reachable"] is False
    assert result["status"] == "unreachable"

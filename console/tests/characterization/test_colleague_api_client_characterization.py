"""Characterization tests for app/colleague_api_client.py (the REAL client).

docs/test-coverage-classification.md previously claimed this module was
"unit-tested," but the only existing test (test_mock_mode.py) exercises
MockColleagueApiClient, a subclass that overrides get_about/
get_event_configurations/call_transaction/get_metadata_manifest and so never
runs this file's own _headers()/URL-construction/session code. These tests
pin the real client's request shape (headers, URL, basic-auth encoding) and
response handling directly, per the "no exemptions" coverage rule.
"""
import base64
from unittest.mock import MagicMock

import pytest

from app.colleague_api_client import ColleagueApiClient, _LegacyTlsAdapter


@pytest.fixture()
def client_with_mock_session():
    c = ColleagueApiClient(base_url="https://colleague.example.edu/", username="svc", password="secret")
    c._session = MagicMock()
    return c


def _mock_response(json_body, status_ok=True):
    resp = MagicMock()
    resp.json.return_value = json_body
    if status_ok:
        resp.raise_for_status.return_value = None
    else:
        import requests
        resp.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
    return resp


def test_base_url_trailing_slash_is_stripped():
    c = ColleagueApiClient(base_url="https://colleague.example.edu/", username="u", password="p")
    assert c.base_url == "https://colleague.example.edu"


def test_is_configured_requires_base_url_and_username():
    assert ColleagueApiClient(base_url="", username="u", password="p").is_configured() is False
    assert ColleagueApiClient(base_url="https://x", username="", password="p").is_configured() is False
    assert ColleagueApiClient(base_url="https://x", username="u", password="p").is_configured() is True


def test_headers_basic_auth_encoding_known_good():
    # Known-good: base64("svc:secret") — if this ever changes, either the
    # encoding logic broke or Colleague's Basic-auth expectations changed.
    c = ColleagueApiClient(base_url="https://x", username="svc", password="secret")
    headers = c._headers()
    expected = base64.b64encode(b"svc:secret").decode()
    assert headers["Authorization"] == f"Basic {expected}"
    assert headers["Accept"] == "application/json"
    assert "Content-Type" not in headers  # intentionally omitted for body-less GETs


def test_get_about_calls_correct_url_and_returns_json(client_with_mock_session):
    c = client_with_mock_session
    c._session.get.return_value = _mock_response({"version": "1.2.3"})
    result = c.get_about()
    assert result == {"version": "1.2.3"}
    args, kwargs = c._session.get.call_args
    assert args[0] == "https://colleague.example.edu/api/about"
    assert kwargs["timeout"] == 15


def test_get_event_configurations_passes_resource_param(client_with_mock_session):
    # Regression: the real EventConfigurationsController takes `event` and
    # `resource` as two separate query params — there is no `resourceName`.
    # The previous version of this method sent exactly that nonexistent
    # param, so every "filtered" call silently returned the full unfiltered
    # list instead (still a 200, nothing ever surfaced the mistake).
    c = client_with_mock_session
    c._session.get.return_value = _mock_response([{"resourceName": "persons"}])
    result = c.get_event_configurations(resource="persons")
    assert result == [{"resourceName": "persons"}]
    args, kwargs = c._session.get.call_args
    assert args[0] == "https://colleague.example.edu/api/event-configurations"
    assert kwargs["params"] == {"resource": "persons"}


def test_get_event_configurations_passes_event_param(client_with_mock_session):
    c = client_with_mock_session
    c._session.get.return_value = _mock_response([])
    c.get_event_configurations(event="AR")
    _, kwargs = c._session.get.call_args
    assert kwargs["params"] == {"event": "AR"}


def test_get_event_configurations_passes_both_params_together(client_with_mock_session):
    c = client_with_mock_session
    c._session.get.return_value = _mock_response([])
    c.get_event_configurations(event="AR", resource="persons")
    _, kwargs = c._session.get.call_args
    assert kwargs["params"] == {"event": "AR", "resource": "persons"}


def test_get_event_configurations_omits_param_when_none(client_with_mock_session):
    c = client_with_mock_session
    c._session.get.return_value = _mock_response([])
    c.get_event_configurations()
    _, kwargs = c._session.get.call_args
    assert kwargs["params"] == {}


def test_call_transaction_posts_to_transactions_path_with_payload(client_with_mock_session):
    c = client_with_mock_session
    c._session.post.return_value = _mock_response({"result": "ok"})
    result = c.call_transaction("GET.PERSON.INFO", {"personId": "1001"})
    assert result == {"result": "ok"}
    args, kwargs = c._session.post.call_args
    assert args[0] == "https://colleague.example.edu/api/transactions/GET.PERSON.INFO"
    assert kwargs["json"] == {"personId": "1001"}
    assert kwargs["timeout"] == 30


def test_call_transaction_raises_on_http_error(client_with_mock_session):
    import requests
    c = client_with_mock_session
    c._session.post.return_value = _mock_response({}, status_ok=False)
    with pytest.raises(requests.HTTPError):
        c.call_transaction("BAD.TRANS", {})


def test_get_metadata_manifest_builds_domain_type_path(client_with_mock_session):
    c = client_with_mock_session
    c._session.get.return_value = _mock_response({"ApiDomain": "person"})
    c.get_metadata_manifest("person", "schema")
    args, _ = c._session.get.call_args
    assert args[0] == "https://colleague.example.edu/api/metadata/manifest/person/schema"


def test_legacy_tls_adapter_only_adds_renegotiation_flag_no_verification_bypass(monkeypatch):
    # Security-relevant characterization: the on-prem-TLS-compat adapter must
    # never disable certificate/hostname verification while relaxing
    # renegotiation tolerance for older IIS/Schannel hosts.
    captured = {}

    def fake_init_poolmanager(self, *args, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "app.colleague_api_client.HTTPAdapter.init_poolmanager",
        fake_init_poolmanager,
    )
    _LegacyTlsAdapter().init_poolmanager()

    ctx = captured["ssl_context"]
    assert ctx.verify_mode.name == "CERT_REQUIRED"
    assert ctx.check_hostname is True

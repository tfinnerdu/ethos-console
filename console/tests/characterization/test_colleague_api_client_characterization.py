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
import http.server
import ssl
import threading
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
import requests

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
    # Regression: create_urllib3_context() alone returns a context with ZERO
    # trusted CA certificates loaded (cert_store_stats() == {'x509': 0,
    # 'crl': 0, 'x509_ca': 0}) — CERT_REQUIRED with nothing to verify against
    # means every single real HTTPS request through this adapter fails
    # CERTIFICATE_VERIFY_FAILED regardless of how valid the actual server
    # certificate is. This went uncaught here for a long time because every
    # other test in this file mocks _session.get/post directly and never
    # performs a real TLS handshake — see the end-to-end test below, which
    # does.
    assert ctx.cert_store_stats()["x509_ca"] > 0


# ── End-to-end TLS handshake — the class of test that would have caught the
# missing-CA-bundle bug above; everything else in this file mocks the
# session and never actually negotiates TLS. ─────────────────────────────────

def _generate_self_signed_cert(tmp_path, common_name="127.0.0.1"):
    """A throwaway self-signed cert/key pair with a SAN, written to tmp_path,
    standing in for a real CA-issued cert — the point is exercising the real
    TLS handshake/verification mechanics, not this specific certificate."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(minutes=5))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(__import__("ipaddress").ip_address(common_name))]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


class _QuietHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ApiDomain": "person"}')

    def log_message(self, *a):
        pass


@pytest.fixture()
def local_https_server(tmp_path):
    cert_path, key_path = _generate_self_signed_cert(tmp_path)
    httpd = http.server.HTTPServer(("127.0.0.1", 0), _QuietHandler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(str(cert_path), str(key_path))
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd.server_address[1], cert_path
    finally:
        httpd.shutdown()
        thread.join(timeout=2)


def test_real_tls_handshake_succeeds_when_ca_is_trusted(local_https_server, monkeypatch):
    # The actual regression test: a real ColleagueApiClient, through the
    # real (unmocked) _LegacyTlsAdapter, against a real TLS listener whose
    # certificate is signed by a CA the adapter has been told to trust.
    port, cert_path = local_https_server
    monkeypatch.setattr("app.colleague_api_client.certifi.where", lambda: str(cert_path))

    client = ColleagueApiClient(base_url=f"https://127.0.0.1:{port}", username="u", password="p")
    result = client.get_metadata_manifest("person", "schema")
    assert result == {"ApiDomain": "person"}


def test_real_tls_handshake_fails_when_ca_is_not_trusted(local_https_server, monkeypatch, tmp_path):
    # Negative control: without the test CA loaded, the same real handshake
    # against the same real server must fail closed, not silently pass —
    # confirms the test above is actually exercising certificate validation.
    port, _real_cert_path = local_https_server
    unrelated_cert_path, _ = _generate_self_signed_cert(tmp_path, common_name="127.0.0.1")
    monkeypatch.setattr("app.colleague_api_client.certifi.where", lambda: str(unrelated_cert_path))

    client = ColleagueApiClient(base_url=f"https://127.0.0.1:{port}", username="u", password="p")
    with pytest.raises(requests.exceptions.SSLError):
        client.get_metadata_manifest("person", "schema")

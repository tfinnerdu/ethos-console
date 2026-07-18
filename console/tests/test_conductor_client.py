"""Tests for app/conductor_client.py's host allow-list.

Regression coverage for an SSRF + API-key-leak bug: trigger_workflow()'s
base_url override let a caller point at any host, and unconditionally
attached the real Conductor API key to that request.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.conductor_client import ConductorClient


@pytest.fixture()
def client():
    return ConductorClient(base_url="https://du-int.doane.edu/prod/conductor", api_key="real-key")


def _mock_response():
    resp = MagicMock()
    resp.text = '"wf-id-123"'
    resp.raise_for_status.return_value = None
    return resp


class TestConfiguredHostAllowedByDefault:
    def test_no_override_uses_configured_host(self, client):
        with patch("app.conductor_client.requests.post", return_value=_mock_response()) as post:
            client.trigger_workflow("wf", {"a": 1})
            assert post.call_args.args[0].startswith("https://du-int.doane.edu")
            assert post.call_args.kwargs["headers"]["X-Authorization"] == "real-key"

    def test_override_matching_configured_host_allowed(self, client):
        with patch("app.conductor_client.requests.post", return_value=_mock_response()) as post:
            client.trigger_workflow("wf", {"a": 1}, base_url="https://du-int.doane.edu/prod/conductor")
            assert post.called


class TestUnlistedHostRejected:
    def test_arbitrary_external_host_rejected(self, client):
        with patch("app.conductor_client.requests.post") as post:
            with pytest.raises(ValueError):
                client.trigger_workflow("wf", {"a": 1}, base_url="https://attacker.example.com")
            post.assert_not_called()  # no request sent — no key exposure

    def test_userinfo_trick_does_not_bypass_allowlist(self, client):
        # "du-int.doane.edu@attacker.example.com" contains the trusted
        # hostname as a substring, but the real host (per URL semantics) is
        # attacker.example.com — a naive `in`/.startswith() check would be
        # fooled by this; a real URL parse must not be.
        with patch("app.conductor_client.requests.post") as post:
            with pytest.raises(ValueError):
                client.trigger_workflow(
                    "wf", {"a": 1},
                    base_url="https://du-int.doane.edu@attacker.example.com/prod/conductor",
                )
            post.assert_not_called()

    def test_subdomain_trick_does_not_bypass_allowlist(self, client):
        with patch("app.conductor_client.requests.post") as post:
            with pytest.raises(ValueError):
                client.trigger_workflow(
                    "wf", {"a": 1}, base_url="https://du-int.doane.edu.attacker.example.com",
                )
            post.assert_not_called()


class TestAdditionalHosts:
    def test_additional_host_allowed_when_listed(self):
        c = ConductorClient(
            base_url="https://du-int.doane.edu/prod/conductor",
            api_key="real-key",
            additional_hosts="du-test.doane.edu, du-stage.doane.edu",
        )
        with patch("app.conductor_client.requests.post", return_value=_mock_response()) as post:
            c.trigger_workflow("wf", {"a": 1}, base_url="https://du-test.doane.edu/prod/conductor")
            assert post.called
            assert post.call_args.kwargs["headers"]["X-Authorization"] == "real-key"

    def test_host_not_in_additional_hosts_still_rejected(self):
        c = ConductorClient(
            base_url="https://du-int.doane.edu/prod/conductor",
            api_key="real-key",
            additional_hosts="du-test.doane.edu",
        )
        with patch("app.conductor_client.requests.post") as post:
            with pytest.raises(ValueError):
                c.trigger_workflow("wf", {"a": 1}, base_url="https://evil.example.com")
            post.assert_not_called()

    def test_empty_additional_hosts_only_allows_configured(self):
        c = ConductorClient(base_url="https://du-int.doane.edu/prod/conductor", api_key="k")
        with patch("app.conductor_client.requests.post") as post:
            with pytest.raises(ValueError):
                c.trigger_workflow("wf", {"a": 1}, base_url="https://du-test.doane.edu")
            post.assert_not_called()

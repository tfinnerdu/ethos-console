"""Tests for app/alerts.py — outbound webhook alerting.

Not previously covered at all (flagged by the pre-launch test-coverage
audit). This is the module that notifies a human when the bus goes silent
or errors spike (app/bus_monitor.py); a silent break here would mean nobody
finds out something is wrong.
"""
from unittest.mock import MagicMock, patch

from app.alerts import send_alert


def test_send_alert_no_op_when_webhook_url_empty():
    with patch("app.alerts.requests.post") as mock_post:
        send_alert("", "title", "message")
    mock_post.assert_not_called()


def test_send_alert_teams_payload_shape():
    mock_resp = MagicMock()
    with patch("app.alerts.requests.post", return_value=mock_resp) as mock_post:
        send_alert("https://xxx.webhook.office.com/webhookb2/abc", "Bus Silence: persons", "No events for 30 min.")

    mock_post.assert_called_once()
    url, kwargs = mock_post.call_args[0][0], mock_post.call_args[1]
    assert url == "https://xxx.webhook.office.com/webhookb2/abc"
    assert kwargs["timeout"] == 10
    payload = kwargs["json"]
    assert payload["type"] == "message"
    card = payload["attachments"][0]["content"]
    text_blocks = card["body"]
    assert text_blocks[0]["text"] == "Bus Silence: persons"
    assert text_blocks[1]["text"] == "No events for 30 min."


def test_send_alert_generic_webhook_payload_shape():
    mock_resp = MagicMock()
    with patch("app.alerts.requests.post", return_value=mock_resp) as mock_post:
        send_alert("https://hooks.slack.com/services/xxx", "Ethos Error Spike", "12 errors in the last hour.")

    mock_post.assert_called_once()
    kwargs = mock_post.call_args[1]
    assert kwargs["json"] == {"text": "*Ethos Error Spike*\n12 errors in the last hour."}


def test_send_alert_raises_for_status_and_swallows_http_error():
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("500 Server Error")
    with patch("app.alerts.requests.post", return_value=mock_resp):
        send_alert("https://hooks.slack.com/services/xxx", "title", "message")
    # No exception propagates — a broken webhook must never break the
    # silence/error-spike check that's calling this.


def test_send_alert_swallows_connection_error():
    with patch("app.alerts.requests.post", side_effect=ConnectionError("refused")):
        send_alert("https://hooks.slack.com/services/xxx", "title", "message")
    # Same guarantee as above, for a transport-level failure instead of an
    # HTTP error status.

"""Outbound webhook alerting for silence and error spike events.

Supports Teams incoming webhooks (webhook.office.com) and Slack/generic
webhooks via a plain {"text": "..."} payload that both accept.
"""
import logging
import requests

log = logging.getLogger(__name__)


def send_alert(webhook_url: str, title: str, message: str) -> None:
    if not webhook_url:
        return

    if "webhook.office.com" in webhook_url:
        payload = {
            "type": "message",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.2",
                    "body": [
                        {"type": "TextBlock", "size": "Medium", "weight": "Bolder", "text": title},
                        {"type": "TextBlock", "text": message, "wrap": True},
                    ],
                },
            }],
        }
    else:
        payload = {"text": f"*{title}*\n{message}"}

    try:
        r = requests.post(webhook_url, json=payload, timeout=10)
        r.raise_for_status()
        log.info("Alert sent: %s", title)
    except Exception as exc:
        log.warning("Alert webhook failed (%s): %s", title, exc)

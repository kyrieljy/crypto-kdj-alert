from __future__ import annotations

import requests

from app.models import AlertEvent
from app.notifiers.base import BaseNotifier, NotifierError


class FeishuWebhookNotifier(BaseNotifier):
    name = "feishu"

    def __init__(self, webhook_url: str, timeout_seconds: int) -> None:
        self._webhook_url = webhook_url
        self._timeout_seconds = timeout_seconds

    def send(self, event: AlertEvent, message: str) -> None:
        if not self._webhook_url:
            return

        try:
            response = requests.post(
                self._webhook_url,
                headers={"Content-Type": "application/json; charset=utf-8"},
                json={"msg_type": "text", "content": {"text": message}},
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise NotifierError(f"Feishu send failed: {exc}") from exc

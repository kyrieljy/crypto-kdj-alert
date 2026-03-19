from __future__ import annotations

import requests

from app.models import AlertEvent
from app.notifiers.base import BaseNotifier, NotifierError


class TelegramNotifier(BaseNotifier):
    name = "telegram"

    def __init__(self, bot_token: str, chat_id: str, timeout_seconds: int) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._timeout_seconds = timeout_seconds

    def send(self, event: AlertEvent, message: str) -> None:
        if not self._bot_token or not self._chat_id:
            return

        try:
            response = requests.post(
                f"https://api.telegram.org/bot{self._bot_token}/sendMessage",
                json={"chat_id": self._chat_id, "text": message},
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise NotifierError(f"Telegram send failed: {exc}") from exc


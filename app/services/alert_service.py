from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from app.models import AlertEvent
from app.notifiers.base import BaseNotifier, NotifierError


SIGNAL_LABELS = {
    "J_CROSS_ABOVE_K": "J\u4e0a\u7a7fK",
    "J_CROSS_BELOW_K": "J\u4e0b\u7a7fK",
    "J_CROSS_ABOVE_K_REPLAY": "J\u4e0a\u7a7fK\uff08\u5386\u53f2\u56de\u653e\uff09",
    "J_CROSS_BELOW_K_REPLAY": "J\u4e0b\u7a7fK\uff08\u5386\u53f2\u56de\u653e\uff09",
    "J_CROSS_ABOVE_K_REPLAY_RESEND": "J\u4e0a\u7a7fK\uff08\u5386\u53f2\u56de\u653e\u91cd\u53d1\uff09",
    "J_CROSS_BELOW_K_REPLAY_RESEND": "J\u4e0b\u7a7fK\uff08\u5386\u53f2\u56de\u653e\u91cd\u53d1\uff09",
    "J_CROSS_BELOW_K_VERIFY": "J\u4e0b\u7a7fK\uff08\u4e2d\u6587\u7f16\u7801\u9a8c\u8bc1\uff09",
    "ONE_MIN_RANGE_ALERT": "1\u5206\u949f\u9ad8\u4f4e\u5dee\u62a5\u8b66",
    "ONE_MIN_VOLUME_ALERT": "1\u5206\u949f\u6210\u4ea4\u91cf\u62a5\u8b66",
    "MA_CROSS_ABOVE": "MA25\u4e0a\u7a7fMA99",
    "MA_CROSS_BELOW": "MA25\u4e0b\u7a7fMA99",
    "TEST_NOTIFICATION": "\u6d4b\u8bd5\u901a\u77e5",
}

SOURCE_ROLE_LABELS = {
    "PRIMARY": "\u4e3b\u6e90",
    "BACKUP": "\u5907\u6e90",
    "VERIFY": "\u9a8c\u8bc1",
    "REPLAY": "\u5386\u53f2\u56de\u653e",
    "TEST": "\u6d4b\u8bd5",
}

DETAIL_LABELS = {
    "range_diff": "\u9ad8\u4f4e\u5dee",
    "threshold": "\u9608\u503c",
    "high_price": "\u6700\u9ad8\u4ef7",
    "low_price": "\u6700\u4f4e\u4ef7",
    "volume": "\u6210\u4ea4\u91cf",
    "fast_ma": "\u5feb\u7ebfMA",
    "slow_ma": "\u6162\u7ebfMA",
}

MA_SIGNALS = {"MA_CROSS_ABOVE", "MA_CROSS_BELOW"}


class AlertService:
    def __init__(self, notifiers: list[BaseNotifier], timezone_name: str, logger: logging.Logger) -> None:
        self._notifiers = notifiers
        self._timezone = ZoneInfo(timezone_name)
        self._logger = logger

    def send(self, event: AlertEvent) -> None:
        message = self._format_message(event)
        for notifier in self._notifiers:
            try:
                notifier.send(event, message)
                self._logger.info("Alert delivered via %s for %s %s", notifier.name, event.symbol, event.signal)
            except NotifierError as exc:
                self._logger.error("Notifier %s failed: %s", notifier.name, exc)

    def _format_message(self, event: AlertEvent) -> str:
        candle_time = datetime.fromtimestamp(event.candle_open_time_ms / 1000, self._timezone)
        trigger_time = datetime.now(self._timezone)
        signal_label = self._render_signal(event.signal)
        source_role_label = self._render_source_role(event.source_role)
        detail_block = self._render_detail(event)
        title = "[MA\u9884\u8b66]" if event.signal in MA_SIGNALS else "[KDJ\u9884\u8b66]"
        return (
            f"{title}\n"
            f"\u6807\u7684: {event.symbol}\n"
            f"\u5468\u671f: {event.interval}\n"
            f"\u4fe1\u53f7: {signal_label}\n"
            f"\u6536\u76d8\u4ef7: {event.close_price:.4f}\n"
            f"{detail_block}"
            f"K\u7ebf\u65f6\u95f4: {candle_time:%Y-%m-%d %H:%M:%S %Z}\n"
            f"\u6570\u636e\u6e90: {source_role_label} ({event.source})\n"
            f"\u63d0\u9192\u65f6\u95f4: {trigger_time:%Y-%m-%d %H:%M:%S %Z}"
        )

    @staticmethod
    def _render_signal(signal: str) -> str:
        return SIGNAL_LABELS.get(signal, signal)

    @staticmethod
    def _render_source_role(source_role: str) -> str:
        return SOURCE_ROLE_LABELS.get(source_role, source_role)

    @staticmethod
    def _render_detail(event: AlertEvent) -> str:
        if not event.detail:
            return f"K: {event.k:.4f}\nD: {event.d:.4f}\nJ: {event.j:.4f}\n"

        lines: list[str] = []
        for raw_line in event.detail.splitlines():
            if "=" not in raw_line:
                lines.append(raw_line)
                continue
            key, value = raw_line.split("=", 1)
            lines.append(f"{DETAIL_LABELS.get(key, key)}: {value}")
        return "\n".join(lines) + "\n"

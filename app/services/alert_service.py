from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from app.models import AlertEvent
from app.notifiers.base import BaseNotifier, NotifierError


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
        return (
            f"[KDJ预警]\n"
            f"标的: {event.symbol}\n"
            f"周期: {event.interval}\n"
            f"信号: {signal_label}\n"
            f"收盘价: {event.close_price:.4f}\n"
            f"K: {event.k:.4f}\n"
            f"D: {event.d:.4f}\n"
            f"J: {event.j:.4f}\n"
            f"K线时间: {candle_time:%Y-%m-%d %H:%M:%S %Z}\n"
            f"数据源: {source_role_label} ({event.source})\n"
            f"提醒时间: {trigger_time:%Y-%m-%d %H:%M:%S %Z}"
        )

    @staticmethod
    def _render_signal(signal: str) -> str:
        mapping = {
            "J_CROSS_ABOVE_K": "J上穿K",
            "J_CROSS_BELOW_K": "J下穿K",
            "J_CROSS_ABOVE_K_REPLAY": "J上穿K（历史回放）",
            "J_CROSS_BELOW_K_REPLAY": "J下穿K（历史回放）",
            "J_CROSS_ABOVE_K_REPLAY_RESEND": "J上穿K（历史回放重发）",
            "J_CROSS_BELOW_K_REPLAY_RESEND": "J下穿K（历史回放重发）",
            "J_CROSS_BELOW_K_VERIFY": "J下穿K（中文编码验证）",
            "TEST_NOTIFICATION": "测试通知",
        }
        return mapping.get(signal, signal)

    @staticmethod
    def _render_source_role(source_role: str) -> str:
        mapping = {
            "PRIMARY": "主源",
            "BACKUP": "备源",
            "VERIFY": "验证",
            "REPLAY": "历史回放",
            "TEST": "测试",
        }
        return mapping.get(source_role, source_role)

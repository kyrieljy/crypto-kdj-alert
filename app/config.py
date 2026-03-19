from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    return int(raw)


@dataclass(frozen=True)
class AppConfig:
    symbols: List[str]
    intervals: List[str]
    kdj_period: int
    k_smoothing: int
    d_smoothing: int
    alert_on_live_candle: bool
    poll_seconds: int
    candle_limit: int
    timezone_name: str
    primary_fail_threshold: int
    primary_recover_probe_seconds: int
    use_okx_only: bool
    use_binance_only: bool
    binance_base_url: str
    okx_base_url: str
    feishu_webhook: str
    telegram_bot_token: str
    telegram_chat_id: str
    notify_feishu: bool
    notify_telegram: bool
    request_timeout_seconds: int
    log_level: str
    state_file: str

    @property
    def has_any_notifier(self) -> bool:
        return (self.notify_feishu and bool(self.feishu_webhook)) or (
            self.notify_telegram and bool(self.telegram_bot_token) and bool(self.telegram_chat_id)
        )


def load_config() -> AppConfig:
    symbols_raw = os.getenv("SYMBOLS", "BTCUSDT,ETHUSDT")
    symbols = [symbol.strip().upper() for symbol in symbols_raw.split(",") if symbol.strip()]
    return AppConfig(
        symbols=symbols,
        intervals=[item.strip() for item in os.getenv("INTERVALS", os.getenv("INTERVAL", "5m")).split(",") if item.strip()],
        kdj_period=_int_env("KDJ_PERIOD", 26),
        k_smoothing=_int_env("K_SMOOTHING", 20),
        d_smoothing=_int_env("D_SMOOTHING", 9),
        alert_on_live_candle=_bool_env("ALERT_ON_LIVE_CANDLE", False),
        poll_seconds=_int_env("POLL_SECONDS", 10),
        candle_limit=_int_env("CANDLE_LIMIT", 200),
        timezone_name=os.getenv("TIMEZONE", "Asia/Shanghai"),
        primary_fail_threshold=_int_env("PRIMARY_FAIL_THRESHOLD", 3),
        primary_recover_probe_seconds=_int_env("PRIMARY_RECOVER_PROBE_SECONDS", 60),
        use_okx_only=_bool_env("USE_OKX_ONLY", True),
        use_binance_only=_bool_env("USE_BINANCE_ONLY", False),
        binance_base_url=os.getenv("BINANCE_BASE_URL", "https://fapi.binance.com"),
        okx_base_url=os.getenv("OKX_BASE_URL", "https://www.okx.com"),
        feishu_webhook=os.getenv("FEISHU_WEBHOOK", "").strip(),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
        notify_feishu=_bool_env("ENABLE_FEISHU", True),
        notify_telegram=_bool_env("ENABLE_TELEGRAM", True),
        request_timeout_seconds=_int_env("REQUEST_TIMEOUT_SECONDS", 10),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        state_file=os.getenv("STATE_FILE", "logs/alert_state.json"),
    )

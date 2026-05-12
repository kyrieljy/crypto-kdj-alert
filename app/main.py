from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv

from app.config import load_config
from app.data_sources.binance import BinanceFuturesDataSource
from app.data_sources.okx import OkxSwapDataSource
from app.data_sources.router import DataSourceRouter
from app.notifiers.feishu import FeishuWebhookNotifier
from app.notifiers.telegram import TelegramNotifier
from app.models import AlertEvent
from app.services.alert_service import AlertService
from app.services.monitor import MonitorService


def build_logger(log_level: str) -> logging.Logger:
    os.makedirs("logs", exist_ok=True)
    logger = logging.getLogger("crypto_kdj_alert")
    logger.setLevel(getattr(logging, log_level, logging.INFO))
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    file_handler = RotatingFileHandler("logs/app.log", maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


def main() -> None:
    load_dotenv()
    config = load_config()
    logger = build_logger(config.log_level)

    if config.use_binance_only:
        primary = BinanceFuturesDataSource(config.binance_base_url, config.request_timeout_seconds)
        secondary = BinanceFuturesDataSource(config.binance_base_url, config.request_timeout_seconds)
        logger.info("Using Binance Futures as the only market data source")
    elif config.use_okx_only:
        primary = OkxSwapDataSource(config.okx_base_url, config.request_timeout_seconds)
        secondary = OkxSwapDataSource(config.okx_base_url, config.request_timeout_seconds)
        logger.info("Using OKX as the only market data source")
    else:
        primary = BinanceFuturesDataSource(config.binance_base_url, config.request_timeout_seconds)
        secondary = OkxSwapDataSource(config.okx_base_url, config.request_timeout_seconds)
    router = DataSourceRouter(
        primary=primary,
        secondary=secondary,
        fail_threshold=config.primary_fail_threshold,
        recover_probe_seconds=config.primary_recover_probe_seconds,
        logger=logger,
    )

    notifiers = []
    if config.notify_feishu:
        notifiers.append(FeishuWebhookNotifier(config.feishu_webhook, config.request_timeout_seconds))
    if config.notify_telegram:
        notifiers.append(
            TelegramNotifier(config.telegram_bot_token, config.telegram_chat_id, config.request_timeout_seconds)
        )
    alert_service = AlertService(notifiers=notifiers, timezone_name=config.timezone_name, logger=logger)

    if not config.has_any_notifier:
        logger.warning("No notifier is fully configured. Alerts will only be logged.")

    if "--test-notify" in sys.argv:
        now_ms = int(datetime.now().timestamp() * 1000)
        kdj_test_event = AlertEvent(
            symbol=config.kdj_symbols[0] if config.kdj_symbols else "ETHUSDT",
            interval=config.intervals[0] if config.intervals else "5m",
            signal="TEST_NOTIFICATION",
            candle_open_time_ms=now_ms,
            close_price=100000.0,
            k=50.0,
            d=45.0,
            j=60.0,
            source="manual_test",
            source_role="TEST",
            detail="K: 50.0000\nD: 45.0000\nJ: 60.0000",
        )
        ma_test_event = AlertEvent(
            symbol=config.ma_symbols[0] if config.ma_symbols else "BTCUSDT",
            interval=config.ma_interval,
            signal="MA_CROSS_ABOVE",
            candle_open_time_ms=now_ms,
            close_price=100000.0,
            k=0.0,
            d=0.0,
            j=0.0,
            source="manual_test",
            source_role="TEST",
            detail="fast_ma=102300.1234\nslow_ma=101980.5678",
        )
        alert_service.send(kdj_test_event)
        alert_service.send(ma_test_event)
        logger.info("Test notification completed")
        return

    monitor = MonitorService(config=config, data_router=router, alert_service=alert_service, logger=logger)
    monitor.run_forever()


if __name__ == "__main__":
    main()

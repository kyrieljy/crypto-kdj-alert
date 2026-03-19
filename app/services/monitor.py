from __future__ import annotations

import json
import logging
import os
import time

from app.config import AppConfig
from app.data_sources.base import DataSourceError
from app.data_sources.router import DataSourceRouter
from app.indicators.kdj import calculate_kdj
from app.models import AlertEvent, IndicatorPoint, SignalSnapshot
from app.services.alert_service import AlertService


class MonitorService:
    def __init__(
        self,
        config: AppConfig,
        data_router: DataSourceRouter,
        alert_service: AlertService,
        logger: logging.Logger,
    ) -> None:
        self._config = config
        self._data_router = data_router
        self._alert_service = alert_service
        self._logger = logger
        self._state_file = config.state_file
        self._signal_state = self._load_state()
        self._one_minute_alerted: dict[tuple[str, str], int] = {}

    def run_forever(self) -> None:
        self._logger.info(
            "Starting monitor for %s on %s using primary/backup routing",
            ",".join(self._config.symbols),
            ",".join(self._config.intervals),
        )
        while True:
            self.run_once()
            time.sleep(self._config.poll_seconds)

    def run_once(self) -> None:
        for symbol in self._config.symbols:
            try:
                self._check_one_minute_alerts(symbol)
            except Exception as exc:  # noqa: BLE001
                self._logger.exception("Unexpected error while checking 1m alerts for %s: %s", symbol, exc)

            for interval in self._config.intervals:
                try:
                    self._check_symbol(symbol, interval)
                except Exception as exc:  # noqa: BLE001
                    self._logger.exception("Unexpected error while checking %s on %s: %s", symbol, interval, exc)

    def _check_symbol(self, symbol: str, interval: str) -> None:
        try:
            candles = self._data_router.fetch_klines(symbol, interval, self._config.candle_limit)
        except DataSourceError as exc:
            self._logger.error("Failed to fetch candles for %s on %s: %s", symbol, interval, exc)
            return

        if self._config.alert_on_live_candle:
            target_candles = candles
        else:
            target_candles = candles[:-1]

        if len(target_candles) < self._config.kdj_period + 1:
            self._logger.warning("Not enough candles for %s on %s", symbol, interval)
            return

        indicators = calculate_kdj(
            candles=target_candles,
            period=self._config.kdj_period,
            k_smoothing=self._config.k_smoothing,
            d_smoothing=self._config.d_smoothing,
        )
        if len(indicators) < 2:
            self._logger.warning("Not enough indicator points for %s", symbol)
            return

        previous_point = indicators[-2]
        current_point = indicators[-1]
        relation = self._relation(current_point)
        state_key = f"{symbol}:{interval}"
        previous_state = self._signal_state.get(state_key)

        if previous_state and previous_state.relation == relation:
            return

        self._signal_state[state_key] = SignalSnapshot(
            symbol=symbol,
            interval=interval,
            candle_open_time_ms=current_point.candle_open_time_ms,
            relation=relation,
        )
        self._save_state()

        signal = self._detect_cross(previous_point, current_point)
        if signal is None:
            return

        event = AlertEvent(
            symbol=symbol,
            interval=interval,
            signal=signal,
            candle_open_time_ms=current_point.candle_open_time_ms,
            close_price=target_candles[-1].close_price,
            k=current_point.k,
            d=current_point.d,
            j=current_point.j,
            source=self._data_router.active_source_name,
            source_role=self._data_router.active_source_role,
        )
        self._alert_service.send(event)

    def _check_one_minute_alerts(self, symbol: str) -> None:
        if not (self._config.one_min_range_alert_enabled or self._config.one_min_volume_alert_enabled):
            return

        candles = self._data_router.fetch_klines(symbol, "1m", max(self._config.candle_limit, 2))
        if len(candles) < 2:
            return

        candle = candles[-1] if self._config.alert_on_live_candle else candles[-2]
        high_low_diff = candle.high_price - candle.low_price

        if self._config.one_min_range_alert_enabled and high_low_diff >= self._config.one_min_range_threshold:
            self._send_one_minute_alert(
                symbol=symbol,
                candle=candle,
                signal="ONE_MIN_RANGE_ALERT",
                dedupe_key=(symbol, "ONE_MIN_RANGE_ALERT"),
                detail=(
                    f"range_diff={high_low_diff:.4f}\n"
                    f"threshold={self._config.one_min_range_threshold}\n"
                    f"high_price={candle.high_price:.4f}\n"
                    f"low_price={candle.low_price:.4f}"
                ),
            )

        if self._config.one_min_volume_alert_enabled and candle.volume > self._config.one_min_volume_threshold:
            self._send_one_minute_alert(
                symbol=symbol,
                candle=candle,
                signal="ONE_MIN_VOLUME_ALERT",
                dedupe_key=(symbol, "ONE_MIN_VOLUME_ALERT"),
                detail=(
                    f"volume={candle.volume:.4f}\n"
                    f"threshold={self._config.one_min_volume_threshold}\n"
                    f"range_diff={high_low_diff:.4f}"
                ),
            )

    def _send_one_minute_alert(
        self,
        symbol: str,
        candle,
        signal: str,
        dedupe_key: tuple[str, str],
        detail: str,
    ) -> None:
        if self._one_minute_alerted.get(dedupe_key) == candle.open_time_ms:
            return

        event = AlertEvent(
            symbol=symbol,
            interval="1m",
            signal=signal,
            candle_open_time_ms=candle.open_time_ms,
            close_price=candle.close_price,
            k=0.0,
            d=0.0,
            j=0.0,
            source=self._data_router.active_source_name,
            source_role=self._data_router.active_source_role,
            detail=detail,
        )
        self._alert_service.send(event)
        self._one_minute_alerted[dedupe_key] = candle.open_time_ms

    @staticmethod
    def _detect_cross(previous_point: IndicatorPoint, current_point: IndicatorPoint) -> str | None:
        if previous_point.j <= previous_point.k and current_point.j > current_point.k:
            return "J_CROSS_ABOVE_K"
        if previous_point.j >= previous_point.k and current_point.j < current_point.k:
            return "J_CROSS_BELOW_K"
        return None

    @staticmethod
    def _relation(point: IndicatorPoint) -> str:
        if point.j > point.k:
            return "above"
        if point.j < point.k:
            return "below"
        return "equal"

    def _load_state(self) -> dict[str, SignalSnapshot]:
        if not os.path.exists(self._state_file):
            return {}
        try:
            with open(self._state_file, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return {}

        state: dict[str, SignalSnapshot] = {}
        for key, value in raw.items():
            try:
                state[key] = SignalSnapshot(
                    symbol=value["symbol"],
                    interval=value["interval"],
                    candle_open_time_ms=int(value["candle_open_time_ms"]),
                    relation=value["relation"],
                )
            except (KeyError, ValueError, TypeError):
                continue
        return state

    def _save_state(self) -> None:
        os.makedirs(os.path.dirname(self._state_file), exist_ok=True)
        payload = {
            key: {
                "symbol": value.symbol,
                "interval": value.interval,
                "candle_open_time_ms": value.candle_open_time_ms,
                "relation": value.relation,
            }
            for key, value in self._signal_state.items()
        }
        with open(self._state_file, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

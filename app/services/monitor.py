from __future__ import annotations

import logging
import json
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
            # Exchange kline endpoints typically include the in-progress candle at the end.
            # Exclude it so alerts are only triggered on confirmed closed candles.
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

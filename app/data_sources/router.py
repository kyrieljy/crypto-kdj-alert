from __future__ import annotations

import logging
import time
from typing import List

from app.data_sources.base import BaseDataSource, DataSourceError
from app.models import Candle


class DataSourceRouter:
    def __init__(
        self,
        primary: BaseDataSource,
        secondary: BaseDataSource,
        fail_threshold: int,
        recover_probe_seconds: int,
        logger: logging.Logger,
    ) -> None:
        self._primary = primary
        self._secondary = secondary
        self._fail_threshold = fail_threshold
        self._recover_probe_seconds = recover_probe_seconds
        self._logger = logger
        self._active = primary
        self._primary_failures = 0
        self._last_probe_at = 0.0

    @property
    def active_source_name(self) -> str:
        return self._active.name

    @property
    def active_source_role(self) -> str:
        if self._active is self._primary:
            return "PRIMARY"
        return "BACKUP"

    def fetch_klines(self, symbol: str, interval: str, limit: int) -> List[Candle]:
        self._maybe_recover_primary(symbol, interval, limit)

        try:
            candles = self._active.fetch_klines(symbol, interval, limit)
            if self._active is self._primary:
                self._primary_failures = 0
            return candles
        except DataSourceError as active_error:
            self._logger.warning("Active data source failed (%s): %s", self._active.name, active_error)

            if self._active is self._primary:
                self._primary_failures += 1
                if self._primary_failures >= self._fail_threshold:
                    self._logger.error("Switching to backup data source after %s failures", self._primary_failures)
                    self._active = self._secondary

            if self._active is self._secondary:
                try:
                    return self._secondary.fetch_klines(symbol, interval, limit)
                except DataSourceError as secondary_error:
                    raise DataSourceError(
                        f"Both data sources failed. primary_or_active={active_error}; secondary={secondary_error}"
                    ) from secondary_error

            try:
                return self._secondary.fetch_klines(symbol, interval, limit)
            except DataSourceError as secondary_error:
                raise DataSourceError(
                    f"Primary failed and backup failed. primary={active_error}; backup={secondary_error}"
                ) from secondary_error

    def _maybe_recover_primary(self, symbol: str, interval: str, limit: int) -> None:
        if self._active is self._primary:
            return

        now = time.time()
        if now - self._last_probe_at < self._recover_probe_seconds:
            return

        self._last_probe_at = now
        try:
            self._primary.fetch_klines(symbol, interval, limit)
        except DataSourceError:
            return

        self._logger.info("Primary data source recovered; switching back to %s", self._primary.name)
        self._active = self._primary
        self._primary_failures = 0

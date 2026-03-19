from __future__ import annotations

from typing import List

import requests

from app.data_sources.base import BaseDataSource, DataSourceError
from app.models import Candle


class BinanceFuturesDataSource(BaseDataSource):
    name = "binance_futures"

    def __init__(self, base_url: str, timeout_seconds: int) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def fetch_klines(self, symbol: str, interval: str, limit: int) -> List[Candle]:
        try:
            response = requests.get(
                f"{self._base_url}/fapi/v1/klines",
                params={"symbol": symbol, "interval": interval, "limit": limit},
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise DataSourceError(f"Binance request failed: {exc}") from exc

        candles: List[Candle] = []
        for row in payload:
            candles.append(
                Candle(
                    symbol=symbol,
                    open_time_ms=int(row[0]),
                    open_price=float(row[1]),
                    high_price=float(row[2]),
                    low_price=float(row[3]),
                    close_price=float(row[4]),
                    volume=float(row[5]),
                    source=self.name,
                )
            )
        return candles


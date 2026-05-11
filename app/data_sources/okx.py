from __future__ import annotations

from typing import List

import requests

from app.data_sources.base import BaseDataSource, DataSourceError
from app.models import Candle


OKX_SYMBOL_MAP = {
    "BTCUSDT": "BTC-USDT-SWAP",
    "ETHUSDT": "ETH-USDT-SWAP",
    "SOLUSDT": "SOL-USDT-SWAP",
    "BNBUSDT": "BNB-USDT-SWAP",
    "ZECUSDT": "ZEC-USDT-SWAP",
}


class OkxSwapDataSource(BaseDataSource):
    name = "okx_swap"

    def __init__(self, base_url: str, timeout_seconds: int) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def fetch_klines(self, symbol: str, interval: str, limit: int) -> List[Candle]:
        inst_id = OKX_SYMBOL_MAP.get(symbol)
        if not inst_id:
            raise DataSourceError(f"Unsupported symbol for OKX: {symbol}")

        okx_bar = self._map_interval(interval)

        try:
            response = requests.get(
                f"{self._base_url}/api/v5/market/history-candles",
                params={"instId": inst_id, "bar": okx_bar, "limit": limit},
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise DataSourceError(f"OKX request failed: {exc}") from exc

        rows = payload.get("data")
        if rows is None:
            raise DataSourceError(f"OKX returned unexpected payload: {payload}")

        candles: List[Candle] = []
        for row in reversed(rows):
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

    @staticmethod
    def _map_interval(interval: str) -> str:
        if interval == "1s":
            return "1s"
        if interval == "5m":
            return "5m"
        if interval == "15m":
            return "15m"
        if interval == "1h":
            return "1H"
        if interval == "1d":
            return "1D"
        raise DataSourceError(f"Unsupported OKX interval: {interval}")

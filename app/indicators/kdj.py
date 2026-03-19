from __future__ import annotations

from typing import Iterable, List

from app.models import Candle, IndicatorPoint


def calculate_kdj(
    candles: Iterable[Candle],
    period: int,
    k_smoothing: int,
    d_smoothing: int,
) -> List[IndicatorPoint]:
    ordered = sorted(candles, key=lambda item: item.open_time_ms)
    if len(ordered) < period:
        return []

    result: List[IndicatorPoint] = []
    prev_k = 50.0
    prev_d = 50.0

    for index, candle in enumerate(ordered):
        if index + 1 < period:
            continue

        window = ordered[index + 1 - period : index + 1]
        low_price = min(item.low_price for item in window)
        high_price = max(item.high_price for item in window)
        if high_price == low_price:
            rsv = 50.0
        else:
            rsv = (candle.close_price - low_price) / (high_price - low_price) * 100.0

        current_k = ((k_smoothing - 1) * prev_k + rsv) / k_smoothing
        current_d = ((d_smoothing - 1) * prev_d + current_k) / d_smoothing
        current_j = 3 * current_k - 2 * current_d

        result.append(
            IndicatorPoint(
                symbol=candle.symbol,
                candle_open_time_ms=candle.open_time_ms,
                k=current_k,
                d=current_d,
                j=current_j,
                source=candle.source,
            )
        )
        prev_k = current_k
        prev_d = current_d

    return result


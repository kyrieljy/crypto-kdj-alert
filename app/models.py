from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Candle:
    symbol: str
    open_time_ms: int
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    source: str


@dataclass(frozen=True)
class IndicatorPoint:
    symbol: str
    candle_open_time_ms: int
    k: float
    d: float
    j: float
    source: str


@dataclass(frozen=True)
class AlertEvent:
    symbol: str
    interval: str
    signal: str
    candle_open_time_ms: int
    close_price: float
    k: float
    d: float
    j: float
    source: str
    source_role: str


@dataclass(frozen=True)
class SignalSnapshot:
    symbol: str
    interval: str
    candle_open_time_ms: int
    relation: str

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from app.models import Candle


class DataSourceError(RuntimeError):
    pass


class BaseDataSource(ABC):
    name: str

    @abstractmethod
    def fetch_klines(self, symbol: str, interval: str, limit: int) -> List[Candle]:
        raise NotImplementedError


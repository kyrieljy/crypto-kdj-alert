from __future__ import annotations

from abc import ABC, abstractmethod

from app.models import AlertEvent


class NotifierError(RuntimeError):
    pass


class BaseNotifier(ABC):
    name: str

    @abstractmethod
    def send(self, event: AlertEvent, message: str) -> None:
        raise NotImplementedError


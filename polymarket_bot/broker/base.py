from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Fill, Order, Position


class Broker(ABC):
    @abstractmethod
    def place_order(self, order: Order) -> Fill:
        ...

    @abstractmethod
    def cancel_order(self, order_id: str, slug: str) -> bool:
        ...

    def refresh(self) -> None:
        """Refresh cached account state (positions/balance). No-op for paper."""
        pass

    @property
    @abstractmethod
    def positions(self) -> list[Position]:
        ...

    @property
    @abstractmethod
    def cash(self) -> float | None:
        # None means "not tracked" (live broker), so cash checks are skipped.
        ...

    @property
    @abstractmethod
    def realized_pnl(self) -> float:
        ...

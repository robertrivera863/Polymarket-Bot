from __future__ import annotations

import time
import uuid

from ..client import PolymarketClient
from ..models import Fill, Order, Position
from .base import Broker


class LiveBroker(Broker):
    """Real Polymarket US order execution (retail API). Requires valid API keys."""

    def __init__(self, client: PolymarketClient):
        self.client = client
        self._positions: list[Position] = []
        self._cash: float | None = None
        self._realized_pnl = 0.0
        self.fills: list[Fill] = []

    def refresh(self) -> None:
        """Pull current positions and balance so risk sees live exposure."""
        try:
            self._positions = self.client.get_positions()
            self._cash, _ = self.client.get_balance()
        except Exception:  # noqa: BLE001 - keep last-known values on transient failure
            pass

    def place_order(self, order: Order) -> Fill:
        order_id = self.client.place_order(order)
        if not order_id:
            order_id = uuid.uuid4().hex
        fill = Fill(
            order_id=order_id,
            slug=order.slug,
            outcome=order.outcome,
            action=order.action,
            price=order.price,
            quantity=order.quantity,
            notional=order.price * order.quantity,
            timestamp=time.time(),
        )
        self.fills.append(fill)
        return fill

    def cancel_order(self, order_id: str, slug: str) -> bool:
        self.client.cancel_order(order_id, slug)
        return True

    @property
    def positions(self) -> list[Position]:
        return self._positions

    @property
    def cash(self) -> float | None:
        return self._cash

    @property
    def realized_pnl(self) -> float:
        return self._realized_pnl

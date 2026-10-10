from __future__ import annotations

import time
import uuid

from ..models import Action, Fill, Order, Outcome, Position
from .base import Broker


class PaperBroker(Broker):
    """Simulated broker: fills immediately at price +/- slippage, tracks cash and positions."""

    def __init__(self, starting_cash: float, slippage: float = 0.0):
        self._cash = starting_cash
        self.starting_cash = starting_cash
        self.slippage = slippage
        self._realized_pnl = 0.0
        self._positions: dict[tuple[str, Outcome], Position] = {}
        self.fills: list[Fill] = []

    def place_order(self, order: Order) -> Fill:
        if order.action == Action.BUY:
            fill_price = order.price * (1 + self.slippage)
        else:
            fill_price = order.price * (1 - self.slippage)

        fill = Fill(
            order_id=uuid.uuid4().hex,
            slug=order.slug,
            outcome=order.outcome,
            action=order.action,
            price=fill_price,
            quantity=order.quantity,
            notional=fill_price * order.quantity,
            timestamp=time.time(),
        )

        key = (order.slug, order.outcome)
        pos = self._positions.get(key)

        if order.action == Action.BUY:
            if pos is None:
                pos = Position(order.slug, order.outcome, 0.0, 0.0)
            total_qty = pos.quantity + order.quantity
            pos.avg_entry_price = (
                pos.avg_entry_price * pos.quantity + fill_price * order.quantity
            ) / total_qty
            pos.quantity = total_qty
            self._cash -= fill.notional
            self._positions[key] = pos
        else:
            if pos is None or order.quantity > pos.quantity + 1e-9:
                raise ValueError(f"insufficient position to sell {order.slug}/{order.outcome.value}")
            self._realized_pnl += (fill_price - pos.avg_entry_price) * order.quantity
            pos.quantity -= order.quantity
            self._cash += fill.notional
            if pos.quantity <= 1e-9:
                del self._positions[key]
            else:
                self._positions[key] = pos

        self.fills.append(fill)
        return fill

    def cancel_order(self, order_id: str, slug: str) -> bool:
        # Paper fills are immediate; nothing rests on the book.
        return False

    @property
    def positions(self) -> list[Position]:
        return list(self._positions.values())

    @property
    def cash(self) -> float | None:
        return self._cash

    @property
    def realized_pnl(self) -> float:
        return self._realized_pnl

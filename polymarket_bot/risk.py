from __future__ import annotations

from dataclasses import dataclass

from .models import Action, Position, Signal


@dataclass
class RiskResult:
    ok: bool
    reason: str = ""


class RiskManager:
    """Hard limits applied to every order, in both paper and live modes."""

    def __init__(self, config):
        self.cfg = config
        self.daily_realized = 0.0

    def check(self, signal: Signal, cash: float | None, positions: list[Position]) -> RiskResult:
        if signal.notional <= 0:
            return RiskResult(False, "notional must be positive")
        if signal.notional > self.cfg.max_order_notional:
            return RiskResult(
                False, f"order notional {signal.notional:.2f} > max {self.cfg.max_order_notional:.2f}"
            )

        pos_notional = sum(
            p.quantity * p.avg_entry_price for p in positions if p.slug == signal.slug
        )
        if pos_notional + signal.notional > self.cfg.max_position_notional:
            return RiskResult(False, "position notional limit exceeded")

        total = sum(p.quantity * p.avg_entry_price for p in positions)
        if total + signal.notional > self.cfg.max_total_exposure:
            return RiskResult(False, "total exposure limit exceeded")

        distinct = len({p.slug for p in positions if p.quantity > 1e-9})
        if signal.action == Action.BUY and pos_notional == 0 and distinct >= self.cfg.max_open_positions:
            return RiskResult(False, "max open positions reached")

        if self.daily_realized <= -self.cfg.max_daily_loss:
            return RiskResult(False, "daily loss limit reached")

        if signal.action == Action.BUY and cash is not None and signal.notional > cash:
            return RiskResult(False, "insufficient cash")

        return RiskResult(True)

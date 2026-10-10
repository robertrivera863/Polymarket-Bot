from __future__ import annotations

import os
import time

from .models import Market, Order


def _stop_requested(stop_file: str) -> bool:
    return bool(stop_file) and os.path.exists(stop_file)


def _interruptible_sleep(seconds: float, stop_file: str) -> bool:
    """Sleep in ~1s slices, returning True early if a stop is requested."""
    if seconds <= 0:
        return _stop_requested(stop_file)
    deadline = time.time() + seconds
    while time.time() < deadline:
        time.sleep(min(1.0, max(0.0, deadline - time.time())))
        if _stop_requested(stop_file):
            return True
    return False


def _price_map(markets: list[Market]) -> dict[str, Market]:
    return {m.slug: m for m in markets}


def compute_equity(broker, markets: list[Market]) -> float:
    by_slug = _price_map(markets)
    equity = broker.cash or 0.0
    for pos in broker.positions:
        m = by_slug.get(pos.slug)
        mark = m.price(pos.outcome) if m else pos.avg_entry_price
        equity += pos.quantity * mark
    return equity


def run_engine(client, broker, strategy, risk, storage, cfg) -> None:
    iteration = 0
    prev_realized = broker.realized_pnl

    while True:
        iteration += 1
        broker.refresh()
        if _stop_requested(cfg.stop_file):
            break
        markets = client.list_markets(closed=False, limit=cfg.max_markets_to_scan)
        signals = strategy.generate(client, markets)
        by_slug = _price_map(markets)

        for sig in signals:
            m = by_slug.get(sig.slug)
            price = sig.price if sig.price is not None else (m.price(sig.outcome) if m else 0.0)
            if price <= 0:
                storage.log_event({"ts": time.time(), "type": "skip", "slug": sig.slug, "reason": "no price"})
                continue

            qty = sig.notional / price
            result = risk.check(sig, broker.cash, broker.positions)
            if not result.ok:
                storage.log_event({"ts": time.time(), "type": "skip", "slug": sig.slug, "reason": result.reason})
                continue

            order = Order(
                slug=sig.slug,
                outcome=sig.outcome,
                action=sig.action,
                price=price,
                quantity=qty,
                notional=sig.notional,
            )
            try:
                fill = broker.place_order(order)
            except Exception as exc:  # noqa: BLE001 - log and continue to next signal
                storage.log_event({"ts": time.time(), "type": "error", "slug": sig.slug, "reason": str(exc)})
                continue

            storage.log_fill(
                {
                    "ts": fill.timestamp,
                    "order_id": fill.order_id,
                    "slug": fill.slug,
                    "outcome": fill.outcome.value,
                    "action": fill.action.value,
                    "price": round(fill.price, 6),
                    "qty": round(fill.quantity, 6),
                    "notional": round(fill.notional, 4),
                }
            )

        risk.daily_realized += broker.realized_pnl - prev_realized
        prev_realized = broker.realized_pnl

        storage.log_event(
            {
                "ts": time.time(),
                "type": "snapshot",
                "iteration": iteration,
                "cash": round(broker.cash or 0.0, 4),
                "equity": round(compute_equity(broker, markets), 4),
                "realized_pnl": round(broker.realized_pnl, 4),
                "open_positions": len(broker.positions),
            }
        )

        if cfg.max_iterations and iteration >= cfg.max_iterations:
            break
        if _interruptible_sleep(cfg.cycle_interval_s, cfg.stop_file):
            break

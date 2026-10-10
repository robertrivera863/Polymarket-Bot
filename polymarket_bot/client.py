from __future__ import annotations

import requests

from .auth import build_auth_headers
from .models import Action, Market, Order, Outcome, Position


def _amount_value(amount) -> float:
    if not isinstance(amount, dict):
        return 0.0
    try:
        return float(amount.get("value") or 0)
    except (TypeError, ValueError):
        return 0.0


class PolymarketClient:
    def __init__(self, config):
        self.config = config
        self._session = requests.Session()

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> "PolymarketClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _auth_headers(self, method: str, path: str) -> dict:
        if not self.config.key_id:
            return {}
        return build_auth_headers(
            method, path, self.config.key_id, self.config.secret_key
        )

    def list_markets(
        self,
        closed: bool = False,
        limit: int = 50,
        category: str | None = None,
        slug: str | None = None,
    ) -> list[Market]:
        path = "/v1/markets"
        params: dict = {"limit": limit}
        if not closed:
            params["closed"] = "false"
        if category:
            params["categories"] = category
        if slug:
            params["slug"] = slug

        resp = self._session.get(self.config.gateway_base + path, params=params, timeout=30)
        resp.raise_for_status()
        return [Market.from_api(m) for m in resp.json().get("markets", [])]

    def get_price_history(
        self, slug: str, interval: str = "INTERVAL_1D", fidelity: int = 5
    ) -> list[dict]:
        path = "/v1/price-history"
        params = {"symbol": slug, "fixedInterval": interval, "fidelity": fidelity}
        resp = self._session.get(self.config.gateway_base + path, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json().get("history", [])

    def place_order(self, order: Order) -> str:
        path = "/v1/orders"
        resp = self._session.post(
            self.config.api_base + path,
            json=self._order_payload(order),
            headers=self._auth_headers("POST", path),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("id", "")

    def cancel_order(self, order_id: str, market_slug: str) -> dict:
        path = f"/v1/order/{order_id}/cancel"
        resp = self._session.post(
            self.config.api_base + path,
            json={"marketSlug": market_slug},
            headers=self._auth_headers("POST", path),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def list_open_orders(self, slugs: list[str] | None = None) -> list[dict]:
        path = "/v1/orders/open"
        params = {"slugs": slugs} if slugs else None
        resp = self._session.get(
            self.config.api_base + path,
            params=params,
            headers=self._auth_headers("GET", path),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("orders", [])

    def get_positions(self, market: str | None = None, limit: int = 100) -> list[Position]:
        path = "/v1/portfolio/positions"
        params: dict = {"limit": limit}
        if market:
            params["market"] = market
        resp = self._session.get(
            self.config.api_base + path,
            params=params,
            headers=self._auth_headers("GET", path),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        positions = data.get("positions", {})
        return [self._parse_position(slug, up) for slug, up in positions.items()]

    @staticmethod
    def _parse_position(slug: str, up: dict) -> Position:
        meta = up.get("marketMetadata", {})
        outcome = Outcome.NO if str(meta.get("outcome", "")).lower() == "no" else Outcome.YES
        try:
            qty = abs(float(up.get("netPositionDecimal") or 0))
        except (TypeError, ValueError):
            qty = 0.0
        cost = _amount_value(up.get("cost"))
        avg_entry_price = cost / qty if qty else 0.0
        return Position(
            slug=meta.get("slug") or slug,
            outcome=outcome,
            quantity=qty,
            avg_entry_price=avg_entry_price,
        )

    def get_balance(self) -> tuple[float, float]:
        """Return (cash, buying_power) for the USD balance, or zeros if unavailable."""
        path = "/v1/account/balances"
        resp = self._session.get(
            self.config.api_base + path,
            headers=self._auth_headers("GET", path),
            timeout=30,
        )
        resp.raise_for_status()
        balances = resp.json().get("balances", [])
        if not balances:
            return 0.0, 0.0
        for b in balances:
            if b.get("currency", "USD") == "USD":
                return float(b.get("currentBalance") or 0), float(b.get("buyingPower") or 0)
        b = balances[0]
        return float(b.get("currentBalance") or 0), float(b.get("buyingPower") or 0)

    def _order_payload(self, order: Order) -> dict:
        intent = {
            (Outcome.YES, Action.BUY): "ORDER_INTENT_BUY_LONG",
            (Outcome.YES, Action.SELL): "ORDER_INTENT_SELL_LONG",
            (Outcome.NO, Action.BUY): "ORDER_INTENT_BUY_SHORT",
            (Outcome.NO, Action.SELL): "ORDER_INTENT_SELL_SHORT",
        }[(order.outcome, order.action)]
        return {
            "marketSlug": order.slug,
            "intent": intent,
            "type": "ORDER_TYPE_LIMIT",
            "price": {"value": f"{order.price:.6f}", "currency": "USD"},
            "quantity": order.quantity,
            "tif": "TIME_IN_FORCE_GOOD_TILL_CANCEL",
        }

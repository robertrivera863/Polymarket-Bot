from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Outcome(str, Enum):
    YES = "yes"
    NO = "no"


class Action(str, Enum):
    BUY = "buy"
    SELL = "sell"


def _parse_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else [parsed]
        except (json.JSONDecodeError, TypeError):
            return [value]
    return [value]


@dataclass
class Market:
    id: str
    slug: str
    question: str
    status: str
    closed: bool
    outcomes: list[str] = field(default_factory=list)
    outcome_prices: list[float] = field(default_factory=list)

    def _index(self, outcome: Outcome) -> int:
        target = outcome.value.lower()
        for i, o in enumerate(self.outcomes):
            if str(o).lower() == target:
                return i
        return 0 if outcome == Outcome.YES else 1

    def price(self, outcome: Outcome) -> float:
        i = self._index(outcome)
        if i < len(self.outcome_prices):
            return self.outcome_prices[i]
        if outcome == Outcome.NO and self.outcome_prices:
            return 1.0 - self.outcome_prices[0]
        return 0.0

    @classmethod
    def from_api(cls, raw: dict) -> "Market":
        prices = [float(p) for p in _parse_list(raw.get("outcomePrices"))]
        return cls(
            id=str(raw.get("id", "")),
            slug=raw.get("slug", ""),
            question=raw.get("question") or raw.get("title", ""),
            status=raw.get("status", ""),
            closed=bool(raw.get("closed", False)),
            outcomes=_parse_list(raw.get("outcomes")),
            outcome_prices=prices,
        )


@dataclass
class Signal:
    slug: str
    outcome: Outcome
    action: Action
    notional: float
    price: float | None = None


@dataclass
class Order:
    slug: str
    outcome: Outcome
    action: Action
    price: float
    quantity: float
    notional: float


@dataclass
class Fill:
    order_id: str
    slug: str
    outcome: Outcome
    action: Action
    price: float
    quantity: float
    notional: float
    timestamp: float


@dataclass
class Position:
    slug: str
    outcome: Outcome
    quantity: float
    avg_entry_price: float

    @property
    def notional(self) -> float:
        return self.quantity * self.avg_entry_price

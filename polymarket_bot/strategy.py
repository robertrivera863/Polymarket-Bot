from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from abc import ABC, abstractmethod

from .client import PolymarketClient
from .models import Action, Market, Outcome, Signal


class Strategy(ABC):
    @abstractmethod
    def generate(self, client: PolymarketClient, markets: list[Market]) -> list[Signal]:
        ...


def _stdev(values: list[float]) -> float:
    n = len(values)
    mean = sum(values) / n
    return (sum((v - mean) ** 2 for v in values) / n) ** 0.5


def _eligible(m: Market) -> bool:
    return (
        not m.closed
        and m.status in ("MARKET_STATUS_OPEN", "INSTRUMENT_STATE_OPEN")
        and len(m.outcome_prices) >= 2
    )


def _signal_from_history(
    m: Market, hist: list[dict], lookback: int, zscore: float, notional: float
) -> Signal | None:
    long_prices = [h.get("longPrice") for h in hist if h.get("longPrice") is not None]
    if len(long_prices) < lookback:
        return None
    window = long_prices[-lookback:]
    sma = sum(window) / lookback
    std = _stdev(window)
    if std <= 1e-9:
        return None
    z = (m.price(Outcome.YES) - sma) / std
    if z < -zscore:
        return Signal(
            slug=m.slug, outcome=Outcome.YES, action=Action.BUY,
            notional=notional, price=m.price(Outcome.YES),
        )
    if z > zscore:
        return Signal(
            slug=m.slug, outcome=Outcome.NO, action=Action.BUY,
            notional=notional, price=m.price(Outcome.NO),
        )
    return None


class MeanReversionStrategy(Strategy):
    """Example heuristic: buy the side that has moved N std-dev below its recent mean.

    Not a proven edge — a transparent starting point to replace with a real model.
    """

    def __init__(
        self,
        lookback: int = 20,
        zscore: float = 1.0,
        max_signals: int = 3,
        notional: float = 10.0,
        concurrency: int = 8,
    ):
        self.lookback = lookback
        self.zscore = zscore
        self.max_signals = max_signals
        self.notional = notional
        self.concurrency = concurrency

    def generate(self, client: PolymarketClient, markets: list[Market]) -> list[Signal]:
        candidates = [m for m in markets if _eligible(m)]

        def _eval(m: Market) -> Signal | None:
            hist = client.get_price_history(m.slug, interval="INTERVAL_1H", fidelity=1)
            return _signal_from_history(m, hist, self.lookback, self.zscore, self.notional)

        with ThreadPoolExecutor(max_workers=self.concurrency) as ex:
            results = list(ex.map(_eval, candidates))

        return [s for s in results if s is not None][: self.max_signals]

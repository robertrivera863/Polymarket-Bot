from polymarket_bot.models import Action, Market, Outcome
from polymarket_bot.strategy import MeanReversionStrategy, _stdev


class FakeClient:
    def __init__(self, history_by_slug):
        self.history_by_slug = history_by_slug

    def get_price_history(self, slug, interval=None, fidelity=None):
        return self.history_by_slug.get(slug, [])


def _market(slug, yes_price, no_price=0.5):
    return Market(
        id="1", slug=slug, question="q", status="MARKET_STATUS_OPEN", closed=False,
        outcomes=["Yes", "No"], outcome_prices=[yes_price, no_price],
    )


def _history(lo=0.4, hi=0.6, n=20):
    return [{"longPrice": (lo if i % 2 == 0 else hi)} for i in range(n)]


def test_stdev():
    assert abs(_stdev([1, 1, 1, 1])) < 1e-12
    assert abs(_stdev([0, 2]) - 1.0) < 1e-12


def test_buys_yes_when_price_far_below_mean():
    client = FakeClient({"m": _history()})
    strat = MeanReversionStrategy(lookback=20, zscore=1.0, max_signals=3, notional=10.0, concurrency=2)
    signals = strat.generate(client, [_market("m", 0.2, 0.8)])
    assert len(signals) == 1
    assert signals[0].outcome == Outcome.YES
    assert signals[0].action == Action.BUY


def test_buys_no_when_price_far_above_mean():
    client = FakeClient({"m": _history()})
    strat = MeanReversionStrategy(lookback=20, zscore=1.0, max_signals=3, notional=10.0, concurrency=2)
    signals = strat.generate(client, [_market("m", 0.8, 0.2)])
    assert len(signals) == 1
    assert signals[0].outcome == Outcome.NO
    assert signals[0].action == Action.BUY


def test_no_signal_when_within_band():
    client = FakeClient({"m": _history()})
    strat = MeanReversionStrategy(lookback=20, zscore=1.0, max_signals=3, notional=10.0, concurrency=2)
    signals = strat.generate(client, [_market("m", 0.5, 0.5)])
    assert signals == []

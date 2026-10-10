from polymarket_bot.config import Config
from polymarket_bot.models import Action, Outcome, Position, Signal
from polymarket_bot.risk import RiskManager


def _cfg(**kw):
    c = Config()
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def _sig(notional=10.0, slug="m", action=Action.BUY, outcome=Outcome.YES):
    return Signal(slug=slug, outcome=outcome, action=action, notional=notional)


def test_order_notional_limit():
    r = RiskManager(_cfg(max_order_notional=10.0))
    res = r.check(_sig(notional=20.0), cash=1000.0, positions=[])
    assert not res.ok
    assert "order notional" in res.reason


def test_position_notional_limit():
    r = RiskManager(_cfg(max_position_notional=25.0, max_order_notional=100.0))
    pos = Position("m", Outcome.YES, 10.0, 1.0)  # 10 notional already held
    res = r.check(_sig(notional=20.0), cash=1000.0, positions=[pos])
    assert not res.ok
    assert "position" in res.reason


def test_total_exposure_limit():
    r = RiskManager(_cfg(max_total_exposure=100.0, max_order_notional=100.0))
    positions = [Position("a", Outcome.YES, 50.0, 1.0), Position("b", Outcome.NO, 40.0, 1.0)]
    res = r.check(_sig(notional=20.0), cash=1000.0, positions=positions)
    assert not res.ok
    assert "exposure" in res.reason


def test_daily_loss_killswitch():
    r = RiskManager(_cfg(max_daily_loss=20.0))
    r.daily_realized = -25.0
    res = r.check(_sig(), cash=1000.0, positions=[])
    assert not res.ok
    assert "daily loss" in res.reason


def test_insufficient_cash():
    r = RiskManager(_cfg())
    res = r.check(_sig(notional=10.0), cash=5.0, positions=[])
    assert not res.ok
    assert "cash" in res.reason


def test_cash_none_skips_cash_check():
    r = RiskManager(_cfg())
    res = r.check(_sig(notional=10.0), cash=None, positions=[])
    assert res.ok


def test_max_open_positions():
    r = RiskManager(_cfg(max_open_positions=1))
    positions = [Position("a", Outcome.YES, 1.0, 1.0)]
    res = r.check(_sig(slug="b"), cash=1000.0, positions=positions)
    assert not res.ok
    assert "open positions" in res.reason


def test_ok():
    r = RiskManager(_cfg())
    res = r.check(_sig(notional=10.0), cash=1000.0, positions=[])
    assert res.ok

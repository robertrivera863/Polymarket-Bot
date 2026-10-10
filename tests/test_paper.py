from polymarket_bot.broker.paper import PaperBroker
from polymarket_bot.models import Action, Order, Outcome


def _buy(broker, slug, outcome, price, notional):
    return broker.place_order(
        Order(
            slug=slug, outcome=outcome, action=Action.BUY,
            price=price, quantity=notional / price, notional=notional,
        )
    )


def test_buy_updates_cash_and_position():
    b = PaperBroker(1000.0)
    _buy(b, "m", Outcome.YES, 0.5, 10.0)
    assert b.cash == 990.0
    assert len(b.positions) == 1
    assert b.positions[0].quantity == 20.0
    assert b.positions[0].avg_entry_price == 0.5


def test_sell_realizes_pnl():
    b = PaperBroker(1000.0)
    _buy(b, "m", Outcome.YES, 0.5, 10.0)  # buy 20 @ 0.50
    b.place_order(
        Order(
            slug="m", outcome=Outcome.YES, action=Action.SELL,
            price=0.7, quantity=20.0, notional=14.0,
        )
    )
    assert abs(b.realized_pnl - 4.0) < 1e-9
    assert len(b.positions) == 0


def test_sell_insufficient_raises():
    b = PaperBroker(1000.0)
    order = Order(
        slug="m", outcome=Outcome.YES, action=Action.SELL,
        price=0.5, quantity=10.0, notional=5.0,
    )
    try:
        b.place_order(order)
    except ValueError:
        return
    raise AssertionError("expected ValueError for oversell")


def test_slippage_on_buy():
    b = PaperBroker(1000.0, slippage=0.01)
    fill = _buy(b, "m", Outcome.YES, 0.5, 10.0)
    assert abs(fill.price - 0.505) < 1e-9


def test_average_entry_price_on_multiple_buys():
    b = PaperBroker(1000.0)
    _buy(b, "m", Outcome.YES, 0.5, 10.0)  # 20 @ 0.50
    _buy(b, "m", Outcome.YES, 0.7, 14.0)  # 20 @ 0.70
    pos = b.positions[0]
    assert pos.quantity == 40.0
    assert abs(pos.avg_entry_price - 0.6) < 1e-9

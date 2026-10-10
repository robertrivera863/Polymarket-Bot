from polymarket_bot.backtest import BacktestTrade, run_walk_forward, summarize


def _hist(prices):
    return [{"timestamp": i, "longPrice": p} for i, p in enumerate(prices)]


def test_walk_forward_buys_yes_on_dip():
    prices = [0.8] * 6 + [0.2, 0.2, 0.8, 0.8, 0.8, 0.8]
    res = run_walk_forward(_hist(prices), lookback=5, zscore=1.0, holding_steps=2, notional=10.0)
    assert res.num_trades == 1
    assert res.trades[0].side == "yes"
    assert res.total_pnl > 0


def test_walk_forward_no_trades_on_flat():
    res = run_walk_forward(_hist([0.5] * 30), lookback=5, zscore=1.0, holding_steps=2, notional=10.0)
    assert res.num_trades == 0


def test_summarize_metrics():
    trades = [
        BacktestTrade("yes", 0, 1, 0.5, 0.6, 10.0),
        BacktestTrade("yes", 1, 2, 0.5, 0.4, -5.0),
    ]
    res = summarize(trades)
    assert res.num_trades == 2
    assert res.total_pnl == 5.0
    assert res.win_rate == 0.5
    assert res.max_drawdown == 5.0
    assert res.profit_factor == 2.0

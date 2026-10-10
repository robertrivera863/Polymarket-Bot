from __future__ import annotations

from dataclasses import dataclass, field

from .strategy import _stdev


@dataclass
class BacktestTrade:
    side: str  # "yes" or "no"
    entry_ts: int
    exit_ts: int
    entry_price: float
    exit_price: float
    pnl: float  # dollar P&L


@dataclass
class BacktestResult:
    trades: list[BacktestTrade] = field(default_factory=list)
    total_pnl: float = 0.0
    num_trades: int = 0
    win_rate: float = 0.0
    max_drawdown: float = 0.0
    profit_factor: float = 0.0


def run_walk_forward(
    history: list[dict], lookback: int, zscore: float, holding_steps: int, notional: float
) -> BacktestResult:
    """Walk-forward backtest of the mean-reversion rule over a longPrice series.

    ``history`` is a list of ``{"timestamp": int, "longPrice": float}`` (ascending).
    A signal at time ``t`` enters at ``longPrice[t]`` and exits at
    ``longPrice[t + holding_steps]``. Buying "no" is modelled as the complement price
    (1 - longPrice), matching the strategy's NO side.
    """
    trades: list[BacktestTrade] = []
    for t in range(lookback, len(history) - holding_steps):
        window = [history[i]["longPrice"] for i in range(t - lookback, t)]
        sma = sum(window) / lookback
        std = _stdev(window)
        if std <= 1e-9:
            continue
        z = (history[t]["longPrice"] - sma) / std

        entry_ts = history[t]["timestamp"]
        exit_ts = history[t + holding_steps]["timestamp"]

        if z < -zscore:
            side = "yes"
            entry = history[t]["longPrice"]
            exit_price = history[t + holding_steps]["longPrice"]
        elif z > zscore:
            side = "no"
            entry = 1 - history[t]["longPrice"]
            exit_price = 1 - history[t + holding_steps]["longPrice"]
        else:
            continue

        qty = notional / entry if entry > 0 else 0.0
        pnl = (exit_price - entry) * qty
        trades.append(BacktestTrade(side, entry_ts, exit_ts, entry, exit_price, pnl))

    return summarize(trades)


def summarize(trades: list[BacktestTrade]) -> BacktestResult:
    total = sum(t.pnl for t in trades)
    n = len(trades)
    wins = sum(1 for t in trades if t.pnl > 0)
    win_rate = wins / n if n else 0.0

    gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
    gross_loss = -sum(t.pnl for t in trades if t.pnl < 0)
    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    else:
        profit_factor = float("inf") if gross_profit > 0 else 0.0

    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in trades:
        equity += t.pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)

    return BacktestResult(
        trades=trades,
        total_pnl=total,
        num_trades=n,
        win_rate=win_rate,
        max_drawdown=max_dd,
        profit_factor=profit_factor,
    )

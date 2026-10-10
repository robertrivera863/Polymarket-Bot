# Polymarket US sports prediction bot

An incremental trading bot for [Polymarket US](https://polymarket.us) — the
US-regulated prediction market. Runs in two modes: **paper** (simulated) and
**live** (real orders, heavily gated).

> ⚠️ Use **Polymarket US** (`polymarket.us`), not international Polymarket. The
> international platform is geo-restricted for US persons.

## Requirements & compatibility

- Python 3.9+ (3.10+ recommended)
- `requests` and `cryptography` — `pip install -r requirements.txt`

Works on **Linux**, **macOS**, and **Windows**. Graceful "Stop" (which saves your
portfolio before exiting) uses a stop-file signal that works on all three
platforms, so every feature behaves the same everywhere.

## What it does

- Lists open sports markets and reads current prices (no keys needed).
- Runs a strategy (mean-reversion example) over live price history.
- Executes through a **paper broker** (simulated fills) or a **live broker**
  (real `POST /v1/orders`), both behind the same hard risk limits.
- Logs every fill and cycle snapshot to JSONL for later review.

## Project layout

```
polymarket_bot/
  config.py     env-driven config (keys, mode, risk limits, strategy params)
  auth.py       Ed25519 request signing for trading endpoints
  client.py     HTTP client (requests + session reuse)
  models.py     Market / Signal / Order / Fill / Position
  broker/       paper.py (simulated) and live.py (real orders)
  risk.py       hard limits: order size, exposure, daily-loss kill switch
  strategy.py   mean-reversion example (replace with a real model)
  engine.py     the run loop
  storage.py    JSONL logs (fills + events)
  cli.py        subcommands: markets, paper, live, backtest, set-keys, set-password, dashboard
```

## Quick start

```bash
cd polymarket-bot
python3 -m venv .venv && source .venv/bin/activate   # or just use system python
pip install -r requirements.txt

# list open markets (read-only, no keys)
python -m polymarket_bot.cli markets --limit 15

# run the paper bot (simulated money, safe)
python -m polymarket_bot.cli paper --iterations 3 --interval 0
```

## Quick Reference (all commands)

```bash
python -m polymarket_bot.cli markets --limit 15      # list open markets (read-only)
python -m polymarket_bot.cli paper                   # simulated trading (safe default)
python -m polymarket_bot.cli live                    # real orders (gated: keys + allow flag)
python -m polymarket_bot.cli backtest --limit 20     # backtest mean-reversion on price history
python -m polymarket_bot.cli set-keys                # store API keys in an encrypted file
python -m polymarket_bot.cli set-password            # set the dashboard password (asks twice)
python -m polymarket_bot.cli dashboard               # web dashboard (controls, backtest, keys)
```

## Web dashboard

Run `python -m polymarket_bot.cli dashboard` and open <http://127.0.0.1:8000>.

Login (HTTP Basic Auth): username `admin`, password from `PM_DASHBOARD_PASSWORD`
(default `Enterbacter` — change it before exposing the dashboard).

Change the password with `python -m polymarket_bot.cli set-password` (it asks twice
and only saves when both entries match), then **restart the dashboard** for the
new password to take effect.

- **Controls** — start/stop the bot (paper or live), set the stop-loss amount
  (`PM_MAX_DAILY_LOSS`), and see whether it's running.
- **Stats** — paper cash/equity/realized P&L, open positions, an equity curve,
  recent fills, and a "load live markets" view.
- **Bot log** — tail of the running bot's output.
- **Command reference** — the full command list, shown right in the page.

It binds to localhost by default for safety; pass `--host 0.0.0.0` to expose it
(use a strong password and ideally HTTPS before doing that on a VPS).

> The dev laptop has no `pip`/`venv`; `requests` + `cryptography` are already
> present there, so `python3 -m polymarket_bot.cli markets` works with system
> Python directly.

## Tests

```bash
python3 tests/run.py            # stdlib runner (no pytest needed)
# or, on a machine with pip:
pip install -r requirements-dev.txt && python -m pytest -q
```

## Live mode (deferred until you've paper-traded a while)

1. Create keys at `polymarket.us/developer`.
2. Copy `.env.example` to `.env` and fill `POLYMARKET_KEY_ID` / `POLYMARKET_SECRET_KEY`.
3. Set `POLYMARKET_ALLOW_LIVE=1` and `POLYMARKET_MODE=live`.
4. Run `python -m polymarket_bot.cli live`.

Live refuses to start unless keys *and* the allow flag are both present, and
order size is capped by `PM_MAX_ORDER_NOTIONAL` (default $10).

## Deployment

See [`deploy.md`](deploy.md) for VPS (Hetzner / AWS Lightsail / Hostinger /
Cloudzy) setup, a systemd unit, and Docker. Use a **US region**.

## Important honesty notes

- The included strategy is a transparent **example**, not a proven edge. Trade
  paper for a long time and review `data/` logs before risking real money.
- Retail prediction markets have rate limits and fees; this bot is built for
  "many trades per hour," not HFT. The institutional gRPC/FIX API is a separate
  onboarding path if you need higher throughput.

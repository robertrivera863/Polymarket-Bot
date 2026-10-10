from __future__ import annotations

import argparse
import json
import signal

from .broker.live import LiveBroker
from .broker.paper import PaperBroker
from .client import PolymarketClient
from .config import Config
from .engine import run_engine
from .risk import RiskManager
from .storage import Storage
from .strategy import MeanReversionStrategy


def _build_strategy(cfg: Config) -> MeanReversionStrategy:
    return MeanReversionStrategy(
        lookback=cfg.mr_lookback,
        zscore=cfg.mr_zscore,
        max_signals=cfg.max_signals_per_cycle,
        notional=cfg.max_order_notional,
        concurrency=cfg.max_concurrency,
    )


def _cmd_set_keys(args) -> None:
    import getpass

    from .secrets import store_keys

    key_id = input("API key ID: ").strip()
    secret = getpass.getpass("API secret key (hidden): ").strip()
    passphrase = getpass.getpass("Protect with a passphrase (hidden): ").strip()
    store_keys(key_id, secret, passphrase, args.path)
    print(f"Encrypted keys stored to {args.path}")
    print("When running live, set POLYMARKET_SECRET_PASSPHRASE=<your passphrase>.")


def _cmd_markets(cfg: Config, args) -> None:
    with PolymarketClient(cfg) as client:
        markets = client.list_markets(
            closed=args.include_closed,
            limit=args.limit,
            category=args.category,
            slug=args.slug,
        )

    if args.json:
        print(json.dumps([m.__dict__ for m in markets], indent=2))
        return
    if not markets:
        print("No markets found.")
        return
    for m in markets:
        pairs = "  ".join(f"{o}@{p}" for o, p in zip(m.outcomes, m.outcome_prices))
        print(f"- {m.question}  [{m.status}]")
        print(f"    slug={m.slug}")
        if pairs:
            print(f"    {pairs}")


def _install_sigterm_handler() -> None:
    def _handler(signum, frame):
        raise KeyboardInterrupt

    try:
        signal.signal(signal.SIGTERM, _handler)
    except (AttributeError, ValueError, OSError):
        pass  # not supported on this platform; the stop-file mechanism still works


def _run(cfg: Config, args, live: bool) -> None:
    _install_sigterm_handler()
    if live:
        if not (cfg.key_id and cfg.secret_key):
            raise SystemExit("Live mode requires POLYMARKET_KEY_ID and POLYMARKET_SECRET_KEY.")
        if not cfg.allow_live:
            raise SystemExit(
                "Live mode is disabled. Set POLYMARKET_ALLOW_LIVE=1 and POLYMARKET_MODE=live to enable."
            )

    if args.iterations is not None:
        cfg.max_iterations = args.iterations
    if args.interval is not None:
        cfg.cycle_interval_s = args.interval
    if args.limit is not None:
        cfg.max_markets_to_scan = args.limit

    with PolymarketClient(cfg) as client:
        broker = LiveBroker(client) if live else PaperBroker(cfg.paper_starting_cash, cfg.paper_slippage)
        risk = RiskManager(cfg)
        strategy = _build_strategy(cfg)
        storage = Storage(cfg.data_dir)

        print(
            f"Running in {'LIVE' if live else 'PAPER'} mode "
            f"(max_order={cfg.max_order_notional}, max_daily_loss={cfg.max_daily_loss}). Ctrl-C to stop."
        )
        try:
            run_engine(client, broker, strategy, risk, storage, cfg)
        except KeyboardInterrupt:
            pass
        finally:
            storage.save_portfolio(broker)
            print("\n--- Summary ---")
            print(f"cash: {broker.cash or 0:.2f}")
            print(f"realized_pnl: {broker.realized_pnl:.2f}")
            print(f"open_positions: {len(broker.positions)}")
            print(f"logs: {cfg.data_dir}/fills.jsonl and {cfg.data_dir}/events.jsonl")


def _cmd_backtest(cfg: Config, args) -> None:
    from .backtest import run_walk_forward

    fidelity = 1 if args.interval in ("INTERVAL_1H", "INTERVAL_6H", "INTERVAL_LIVE") else 5
    with PolymarketClient(cfg) as client:
        markets = client.list_markets(
            closed=args.include_closed, limit=args.limit, slug=args.slug
        )
        if not markets:
            print("No markets found.")
            return
        grand_total = 0.0
        grand_trades = 0
        for m in markets:
            hist = client.get_price_history(m.slug, interval=args.interval, fidelity=fidelity)
            res = run_walk_forward(hist, args.lookback, args.zscore, args.holding, args.notional)
            if res.num_trades == 0:
                continue
            grand_total += res.total_pnl
            grand_trades += res.num_trades
            print(
                f"{m.slug}: trades={res.num_trades} pnl={res.total_pnl:+.2f} "
                f"win%={res.win_rate:.0%} maxDD={res.max_drawdown:.2f} PF={res.profit_factor:.2f}"
            )
        print(f"\nTOTAL: trades={grand_trades} pnl={grand_total:+.2f}")


def _cmd_set_password(args) -> None:
    import getpass

    from .secrets import store_password

    pw1 = getpass.getpass("New dashboard password (hidden): ").strip()
    if not pw1:
        raise SystemExit("Aborted: password cannot be empty.")
    pw2 = getpass.getpass("Confirm password (hidden): ").strip()
    if pw1 != pw2:
        raise SystemExit("Passwords do not match — nothing saved.")
    store_password(pw1, args.path)
    print(f"Password saved to {args.path}.")
    print("Restart the dashboard for the new password to take effect.")


def _cmd_dashboard(cfg: Config, args) -> None:
    from .web import DASHBOARD_USERNAME, run_server

    msg = (
        "Polymarket Bot dashboard\n"
        f"  URL:       http://{args.host}:{args.port}\n"
        f"  Username:  {DASHBOARD_USERNAME}\n"
        f"  Password:  {cfg.dashboard_password}\n"
        "To run it: python3 -m polymarket_bot.cli dashboard\n"
        "  then open the URL above in your browser.\n"
        "Ctrl-C to stop."
    )
    print(msg, flush=True)
    run_server(cfg, args.host, args.port)


def main() -> None:
    parser = argparse.ArgumentParser(prog="polymarket-bot")
    sub = parser.add_subparsers(dest="command", required=True)

    m = sub.add_parser("markets", help="List open markets (read-only)")
    m.add_argument("--limit", type=int, default=20)
    m.add_argument("--category", default=None)
    m.add_argument("--slug", default=None)
    m.add_argument("--include-closed", action="store_true")
    m.add_argument("--json", action="store_true")

    for name in ("paper", "live"):
        r = sub.add_parser(name, help=f"Run the bot in {name} mode")
        r.add_argument("--iterations", type=int, default=None)
        r.add_argument("--interval", type=float, default=None)
        r.add_argument("--limit", type=int, default=None)

    s = sub.add_parser("set-keys", help="Store API keys in an encrypted file")
    s.add_argument("--path", default="secrets.enc", help="Output file path")

    pw = sub.add_parser(
        "set-password",
        help="Set the dashboard password (asks twice; restart dashboard to apply)",
        epilog="Note: restart the dashboard after changing the password for it to take effect.",
    )
    pw.add_argument("--path", default=".dashboard_password", help="Password file path")

    b = sub.add_parser("backtest", help="Backtest the mean-reversion strategy on price history")
    b.add_argument("--limit", type=int, default=20)
    b.add_argument("--slug", default=None)
    b.add_argument("--include-closed", action="store_true")
    b.add_argument("--lookback", type=int, default=20)
    b.add_argument("--zscore", type=float, default=1.0)
    b.add_argument("--holding", type=int, default=3)
    b.add_argument("--notional", type=float, default=10.0)
    b.add_argument("--interval", default="INTERVAL_1H")

    d = sub.add_parser("dashboard", help="Serve a local web dashboard")
    d.add_argument("--host", default="127.0.0.1")
    d.add_argument("--port", type=int, default=8000)

    args = parser.parse_args()
    cfg = Config.from_env()

    if args.command == "markets":
        _cmd_markets(cfg, args)
    elif args.command == "set-keys":
        _cmd_set_keys(args)
    elif args.command == "set-password":
        _cmd_set_password(args)
    elif args.command == "backtest":
        _cmd_backtest(cfg, args)
    elif args.command == "dashboard":
        _cmd_dashboard(cfg, args)
    else:
        _run(cfg, args, live=(args.command == "live"))


if __name__ == "__main__":
    main()

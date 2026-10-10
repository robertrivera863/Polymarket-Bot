import json
import os
import sys
import tempfile

from polymarket_bot.broker.paper import PaperBroker
from polymarket_bot.config import Config, _load_dashboard_password
from polymarket_bot.models import Action, Order, Outcome
from polymarket_bot.secrets import store_password
from polymarket_bot.storage import Storage
from polymarket_bot.web import BotController, Dashboard, check_basic_auth


def _write(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def test_summary_reads_logs_and_portfolio():
    with tempfile.TemporaryDirectory() as d:
        _write(os.path.join(d, "fills.jsonl"), [{"slug": "m", "outcome": "yes", "action": "buy", "price": 0.5, "qty": 20, "notional": 10}])
        _write(os.path.join(d, "events.jsonl"), [{"type": "snapshot", "iteration": 1, "equity": 1000.0}])
        with open(os.path.join(d, "portfolio.json"), "w") as f:
            json.dump({"cash": 990.0, "realized_pnl": 0.0, "positions": []}, f)

        s = Dashboard(Config(data_dir=d)).summary()
        assert s["fills_count"] == 1
        assert s["portfolio"]["cash"] == 990.0
        assert s["last_snapshot"]["equity"] == 1000.0


def test_equity_series_only_snapshots():
    with tempfile.TemporaryDirectory() as d:
        _write(os.path.join(d, "events.jsonl"), [
            {"type": "fill", "slug": "m"},
            {"type": "snapshot", "iteration": 1, "equity": 100.0},
        ])
        eq = Dashboard(Config(data_dir=d)).equity_series()
        assert len(eq) == 1
        assert eq[0]["equity"] == 100.0


def test_save_portfolio():
    with tempfile.TemporaryDirectory() as d:
        b = PaperBroker(1000.0)
        b.place_order(Order("m", Outcome.YES, Action.BUY, 0.5, 20.0, 10.0))
        Storage(d).save_portfolio(b)
        with open(os.path.join(d, "portfolio.json")) as f:
            data = json.load(f)
        assert data["cash"] == 990.0
        assert data["positions"][0]["slug"] == "m"
        assert data["positions"][0]["quantity"] == 20.0


def test_controller_initial_status():
    with tempfile.TemporaryDirectory() as d:
        c = BotController(d)
        assert c.status()["running"] is False


def test_controller_start_and_stop():
    with tempfile.TemporaryDirectory() as d:
        c = BotController(d, graceful_timeout=0.5)
        cmd = [sys.executable, "-c", "import time; time.sleep(30)"]
        st = c.start("paper", 25.0, command=cmd)
        assert st["running"] is True
        assert st["stop_loss"] == 25.0
        st = c.stop()
        assert st["running"] is False


def test_basic_auth():
    import base64

    assert check_basic_auth("", "pw") is False
    ok = "Basic " + base64.b64encode(b"admin:pw").decode()
    assert check_basic_auth(ok, "pw") is True
    assert check_basic_auth("Basic wrong", "pw") is False
    assert check_basic_auth("", "") is True  # empty password disables auth


def test_store_and_load_password():
    os.environ.pop("PM_DASHBOARD_PASSWORD", None)
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "pw.txt")
        store_password("secret123", path)
        assert _load_dashboard_password(path) == "secret123"

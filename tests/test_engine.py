import os
import tempfile
import threading
import time

from polymarket_bot.engine import _interruptible_sleep, _stop_requested


def test_stop_requested():
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, ".stop")
        assert _stop_requested(f) is False
        assert _stop_requested("") is False  # empty stop_file never triggers
        open(f, "w").close()
        assert _stop_requested(f) is True


def test_interruptible_sleep_stops_early():
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, ".stop")
        t = threading.Timer(0.2, lambda: open(f, "w").close())
        t.start()
        start = time.time()
        stopped = _interruptible_sleep(10.0, f)
        elapsed = time.time() - start
        t.cancel()
        assert stopped is True
        assert elapsed < 3.0

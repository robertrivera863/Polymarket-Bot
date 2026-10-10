"""Minimal stdlib test runner (no pytest required).

Usage: python3 tests/run.py
"""
import importlib
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

MODULES = [
    "tests.test_models",
    "tests.test_risk",
    "tests.test_paper",
    "tests.test_strategy",
    "tests.test_secrets",
    "tests.test_backtest",
    "tests.test_web",
    "tests.test_engine",
]


def main() -> int:
    passed = failed = 0
    for mn in MODULES:
        mod = importlib.import_module(mn)
        for name in sorted(dir(mod)):
            if not name.startswith("test_"):
                continue
            try:
                getattr(mod, name)()
                passed += 1
                print(f"PASS {mn}.{name}")
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"FAIL {mn}.{name}: {exc!r}")
                traceback.print_exc()
    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

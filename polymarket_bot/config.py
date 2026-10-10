import os
from dataclasses import dataclass

DEFAULT_API_BASE = "https://api.polymarket.us"
DEFAULT_GATEWAY_BASE = "https://gateway.polymarket.us"
PASSWORD_FILE = ".dashboard_password"


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass


def _load_dashboard_password(path: str = PASSWORD_FILE) -> str:
    env_pw = os.getenv("PM_DASHBOARD_PASSWORD")
    if env_pw:
        return env_pw
    if os.path.exists(path):
        with open(path) as f:
            pw = f.read().strip()
            if pw:
                return pw
    return "Enterbacter"


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw not in (None, "") else default


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw not in (None, "") else default


def _apply_secrets(cfg) -> None:
    """Fill in API keys from the encrypted secrets file when env vars are unset."""
    if cfg.key_id and cfg.secret_key:
        return
    passphrase = os.getenv("POLYMARKET_SECRET_PASSPHRASE", "")
    path = os.getenv("POLYMARKET_SECRETS_FILE", "secrets.enc")
    if not passphrase or not os.path.exists(path):
        return
    try:
        from .secrets import load_keys

        cfg.key_id, cfg.secret_key = load_keys(passphrase, path)
    except Exception:  # noqa: BLE001 - wrong passphrase/corrupt file: stay read-only
        pass


@dataclass
class Config:
    # API credentials / endpoints
    key_id: str = ""
    secret_key: str = ""
    api_base: str = DEFAULT_API_BASE
    gateway_base: str = DEFAULT_GATEWAY_BASE

    # Mode
    mode: str = "paper"  # "paper" or "live"
    allow_live: bool = False

    # Risk limits (USD / counts)
    max_order_notional: float = 10.0
    max_position_notional: float = 25.0
    max_total_exposure: float = 100.0
    max_daily_loss: float = 20.0
    max_open_positions: int = 10

    # Engine
    cycle_interval_s: float = 5.0
    max_iterations: int = 0  # 0 = run forever
    max_markets_to_scan: int = 100
    max_concurrency: int = 8
    stop_file: str = ""  # if set, the engine exits gracefully when this file appears

    # Paper broker
    paper_starting_cash: float = 1000.0
    paper_slippage: float = 0.0

    # Strategy (mean reversion example)
    strategy: str = "mean_reversion"
    mr_lookback: int = 20
    mr_zscore: float = 1.0
    max_signals_per_cycle: int = 3

    # Storage
    data_dir: str = "data"

    # Dashboard
    dashboard_password: str = "Enterbacter"

    @classmethod
    def from_env(cls) -> "Config":
        _load_dotenv()
        cfg = cls(
            key_id=os.getenv("POLYMARKET_KEY_ID", ""),
            secret_key=os.getenv("POLYMARKET_SECRET_KEY", ""),
            api_base=os.getenv("POLYMARKET_API_BASE", DEFAULT_API_BASE),
            gateway_base=os.getenv("POLYMARKET_GATEWAY_BASE", DEFAULT_GATEWAY_BASE),
            mode=os.getenv("POLYMARKET_MODE", "paper"),
            allow_live=os.getenv("POLYMARKET_ALLOW_LIVE", "0") == "1",
            max_order_notional=_float_env("PM_MAX_ORDER_NOTIONAL", 10.0),
            max_position_notional=_float_env("PM_MAX_POSITION_NOTIONAL", 25.0),
            max_total_exposure=_float_env("PM_MAX_TOTAL_EXPOSURE", 100.0),
            max_daily_loss=_float_env("PM_MAX_DAILY_LOSS", 20.0),
            max_open_positions=_int_env("PM_MAX_OPEN_POSITIONS", 10),
            cycle_interval_s=_float_env("PM_CYCLE_INTERVAL_S", 5.0),
            max_iterations=_int_env("PM_MAX_ITERATIONS", 0),
            max_markets_to_scan=_int_env("PM_MAX_MARKETS_TO_SCAN", 100),
            max_concurrency=_int_env("PM_MAX_CONCURRENCY", 8),
            stop_file=os.getenv("PM_STOP_FILE", ""),
            paper_starting_cash=_float_env("PM_PAPER_STARTING_CASH", 1000.0),
            paper_slippage=_float_env("PM_PAPER_SLIPPAGE", 0.0),
            strategy=os.getenv("PM_STRATEGY", "mean_reversion"),
            mr_lookback=_int_env("PM_MR_LOOKBACK", 20),
            mr_zscore=_float_env("PM_MR_ZSCORE", 1.0),
            max_signals_per_cycle=_int_env("PM_MAX_SIGNALS", 3),
            data_dir=os.getenv("PM_DATA_DIR", "data"),
            dashboard_password=_load_dashboard_password(),
        )
        _apply_secrets(cfg)
        return cfg

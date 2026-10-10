import json
import os
import time


class Storage:
    """Append-only JSONL logs for fills and engine events."""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.fills_path = os.path.join(data_dir, "fills.jsonl")
        self.events_path = os.path.join(data_dir, "events.jsonl")

    def log_fill(self, record: dict) -> None:
        self._append(self.fills_path, record)

    def log_event(self, record: dict) -> None:
        self._append(self.events_path, record)

    def save_portfolio(self, broker) -> None:
        """Snapshot the broker's cash, realized P&L, and positions to JSON."""
        path = os.path.join(self.data_dir, "portfolio.json")
        data = {
            "cash": broker.cash,
            "realized_pnl": broker.realized_pnl,
            "positions": [
                {
                    "slug": p.slug,
                    "outcome": p.outcome.value,
                    "quantity": p.quantity,
                    "avg_entry_price": p.avg_entry_price,
                }
                for p in broker.positions
            ],
            "updated_at": time.time(),
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def _append(path: str, record: dict) -> None:
        with open(path, "a") as f:
            f.write(json.dumps(record) + "\n")

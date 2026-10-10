# Deployment guide

## Pick a US region

Polymarket US is a US-regulated platform. Run your bot from a **US region** so it
can reach the API without geo-restrictions. All of the providers you mentioned have
US regions:

| Provider | US region example |
|---|---|
| Hetzner | `us-east` (Ashburn, VA) or `us-west` (Hillsboro, OR) |
| AWS Lightsail | `us-east-1`, `us-west-2` |
| Hostinger | any US VPS location |
| Cloudzy | any US location |

Any provider works — the API is plain HTTPS, so the only requirement is a US exit
and outbound internet access.

## Setup (systemd on a VPS)

```bash
# 1. Get the code on the box
git clone <your-repo-url> polymarket-bot && cd polymarket-bot

# 2. Install dependencies (this machine has pip; unlike the dev laptop)
sudo apt update && sudo apt install -y python3-venv
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# edit .env: set POLYMARKET_KEY_ID / POLYMARKET_SECRET_KEY for live mode
```

### systemd unit (paper)

`/etc/systemd/system/polymarket-paper.service`:

```ini
[Unit]
Description=Polymarket bot (paper)
After=network-online.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/polymarket-bot
ExecStart=/home/ubuntu/polymarket-bot/.venv/bin/python -m polymarket_bot.cli paper
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now polymarket-paper
journalctl -u polymarket-paper -f
```

### Docker (alternative)

```bash
docker build -t polymarket-bot .
docker run --rm -it --env-file .env polymarket-bot          # paper (default)
docker run --rm -it --env-file .env polymarket-bot python -m polymarket_bot.cli paper
```

## Configuration (env vars)

| Variable | Default | Meaning |
|---|---|---|
| `POLYMARKET_KEY_ID` / `POLYMARKET_SECRET_KEY` | — | API credentials (live mode only) |
| `POLYMARKET_MODE` | `paper` | `paper` or `live` |
| `POLYMARKET_ALLOW_LIVE` | `0` | Must be `1` for live orders |
| `PM_MAX_ORDER_NOTIONAL` | `10` | Max USD per order |
| `PM_MAX_POSITION_NOTIONAL` | `25` | Max USD per market |
| `PM_MAX_TOTAL_EXPOSURE` | `100` | Max USD across all positions |
| `PM_MAX_DAILY_LOSS` | `20` | Kill switch: block new orders after this realized loss |
| `PM_MAX_OPEN_POSITIONS` | `10` | Max distinct markets held |
| `PM_CYCLE_INTERVAL_S` | `5` | Seconds between engine cycles |
| `PM_MAX_CONCURRENCY` | `8` | Concurrent price-history fetches |
| `PM_PAPER_STARTING_CASH` | `1000` | Paper bankroll |
| `PM_DATA_DIR` | `data` | Where fills/events logs go |

## Live mode safety rails

- Live mode **refuses to start** unless `POLYMARKET_KEY_ID`, `POLYMARKET_SECRET_KEY`,
  `POLYMARKET_ALLOW_LIVE=1`, and `POLYMARKET_MODE=live` are all set.
- Order-level notional is capped; set `PM_MAX_ORDER_NOTIONAL` small at first.
- **Known limitation:** the retail API's full position/balance endpoint isn't wired
  yet, so live risk currently enforces order-level limits only (not exposure). Keep
  `PM_MAX_ORDER_NOTIONAL` tiny until position tracking is added.
- The current strategy is a mean-reversion *example*, not a proven edge. Run paper
  for a long time and review `data/fills.jsonl` / `data/events.jsonl` before going live.

## Throughput notes

"Many trades per hour" is modest for this architecture: each cycle fans out
price-history fetches across `PM_MAX_CONCURRENCY` threads, and the retail API has
rate limits that cap real throughput anyway. True low-latency/HFT is not a fit for
retail prediction markets (fees + rate limits); the institutional gRPC/FIX API
(separate onboarding via `onboarding@polymarket.us`) is the higher-throughput path
if you ever need it.

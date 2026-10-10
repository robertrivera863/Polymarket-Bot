from __future__ import annotations

import base64
import json
import os
import signal
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .client import PolymarketClient
from .config import Config

DASHBOARD_USERNAME = "admin"


def check_basic_auth(auth_header: str, password: str) -> bool:
    if not password:
        return True
    expected = "Basic " + base64.b64encode(f"{DASHBOARD_USERNAME}:{password}".encode()).decode()
    return auth_header == expected

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Polymarket Bot</title>
<style>
  :root { --bg:#0e1117; --panel:#161b22; --border:#30363d; --text:#e6edf3;
          --muted:#8b949e; --green:#3fb950; --red:#f85149; --accent:#58a6ff; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
         background:var(--bg); color:var(--text); }
  header { display:flex; align-items:center; gap:12px; padding:16px 24px;
           border-bottom:1px solid var(--border); }
  header h1 { font-size:18px; margin:0; }
  .badge { padding:2px 10px; border-radius:12px; font-size:12px; font-weight:600; }
  .paper { background:#1f6feb33; color:#58a6ff; }
  .live { background:#f8514933; color:#f85149; }
  .container { padding:24px; max-width:1000px; margin:0 auto; }
  .cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
           gap:12px; margin-bottom:24px; }
  .card { background:var(--panel); border:1px solid var(--border);
          border-radius:8px; padding:16px; }
  .card .label { font-size:12px; color:var(--muted); text-transform:uppercase;
                 letter-spacing:.04em; }
  .card .value { font-size:24px; font-weight:600; margin-top:4px; }
  .pos { color:var(--green); } .neg { color:var(--red); }
  section { background:var(--panel); border:1px solid var(--border);
            border-radius:8px; padding:16px; margin-bottom:24px; }
  h2 { font-size:13px; margin:0 0 12px; color:var(--muted); text-transform:uppercase;
       letter-spacing:.04em; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th, td { text-align:left; padding:6px 8px; border-bottom:1px solid var(--border); }
  th { color:var(--muted); font-weight:500; }
  button { background:var(--accent); color:#0d1117; border:none; padding:8px 14px;
           border-radius:6px; font-weight:600; cursor:pointer; }
  button:hover { opacity:.9; }
  button.stop { background:var(--red); color:#fff; }
  button.start { background:var(--green); color:#0d1117; }
  .muted { color:var(--muted); }
  input, select { background:#0d1117; color:var(--text); border:1px solid var(--border);
                  border-radius:6px; padding:6px 8px; }
  svg { width:100%; height:180px; display:block; }
  pre { font-size:12px; color:var(--muted); overflow-x:auto; }
  .logbox { background:#0d1117; padding:12px; border-radius:6px; max-height:220px;
            overflow:auto; font-family:ui-monospace,monospace; font-size:12px; white-space:pre-wrap; }
  .controls { display:flex; align-items:center; gap:12px; flex-wrap:wrap; }
  .controls label { font-size:13px; color:var(--muted); display:flex; align-items:center; gap:6px; }
  .dot { font-weight:700; }
</style>
</head>
<body>
<header>
  <h1>Polymarket Bot</h1>
  <span id="mode" class="badge paper">…</span>
  <span class="muted" style="margin-left:auto" id="updated"></span>
  <button onclick="refreshAll()">Refresh</button>
</header>
<div class="container">

  <section>
    <h2>Bot controls</h2>
    <div class="controls">
      <span id="botStatus" class="dot muted">● Stopped</span>
      <label>Mode
        <select id="modeSelect">
          <option value="paper" selected>paper</option>
          <option value="live">live</option>
        </select>
      </label>
      <label>Stop loss ($)
        <input id="stopLoss" type="number" value="20" min="0" step="1" style="width:80px">
      </label>
      <button class="start" onclick="startBot()">▶ Start</button>
      <button class="stop" onclick="stopBot()">■ Stop</button>
    </div>
    <div class="muted" style="margin-top:8px" id="botDetail"></div>
  </section>

  <div class="cards">
    <div class="card"><div class="label">Cash</div><div class="value" id="cash">–</div></div>
    <div class="card"><div class="label">Equity</div><div class="value" id="equity">–</div></div>
    <div class="card"><div class="label">Realized P&amp;L</div><div class="value" id="pnl">–</div></div>
    <div class="card"><div class="label">Open Positions</div><div class="value" id="positions">–</div></div>
    <div class="card"><div class="label">Total Fills</div><div class="value" id="fills">–</div></div>
  </div>

  <section>
    <h2>Equity over time</h2>
    <svg id="chart" viewBox="0 0 600 180" preserveAspectRatio="none"></svg>
  </section>

  <section>
    <h2>Recent fills</h2>
    <div id="fillsTable"></div>
  </section>

  <section>
    <h2>Open markets
      <button onclick="loadMarkets()" style="float:right">Load live markets</button>
    </h2>
    <div id="marketsTable"><div class="muted">Click "Load live markets" to fetch.</div></div>
  </section>

  <section>
    <h2>Backtest</h2>
    <div class="controls">
      <label>Markets <input id="btLimit" type="number" value="10" min="1" style="width:70px"></label>
      <label>Lookback <input id="btLookback" type="number" value="20" min="2" style="width:70px"></label>
      <label>Holding <input id="btHolding" type="number" value="3" min="1" style="width:60px"></label>
      <label>Notional $ <input id="btNotional" type="number" value="10" min="0" style="width:80px"></label>
      <button onclick="runBacktest()">Run backtest</button>
    </div>
    <div id="btResults" class="muted" style="margin-top:8px">Not run yet.</div>
  </section>

  <section>
    <h2>API keys (for live trading)</h2>
    <div style="display:flex; flex-direction:column; gap:8px; max-width:400px">
      <input id="keyId" type="text" placeholder="Key ID">
      <input id="secretKey" type="password" placeholder="Secret key">
      <input id="keyPass" type="password" placeholder="Passphrase (encrypts the keys)">
      <button onclick="saveKeys()">Save keys (encrypted)</button>
    </div>
    <div id="keysMsg" class="muted" style="margin-top:8px"></div>
  </section>

  <section>
    <h2>Bot log <button onclick="refreshLog()" style="float:right">Refresh</button></h2>
    <div id="logBox" class="logbox">(no log yet)</div>
  </section>

  <section>
    <h2>Command reference</h2>
    <pre>python3 -m polymarket_bot.cli markets --limit 15   # list open markets (read-only)
python3 -m polymarket_bot.cli paper                  # simulated trading (safe)
python3 -m polymarket_bot.cli live                   # real orders (needs keys + allow flag)
python3 -m polymarket_bot.cli backtest --limit 20    # backtest the strategy
python3 -m polymarket_bot.cli set-keys               # store API keys encrypted
python3 -m polymarket_bot.cli set-password           # set the dashboard password
python3 -m polymarket_bot.cli dashboard              # this web interface</pre>
    <div class="muted" style="margin-top:8px">After changing the password with <code>set-password</code>, restart the dashboard for it to take effect.</div>
  </section>
</div>

<script>
async function get(url){ const r = await fetch(url); return r.json(); }
async function post(url, body){
  const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  return r.json();
}
function fmt(x){ return (x==null || isNaN(x)) ? '–' : Number(x).toFixed(2); }
function pnlClass(x){ return (x||0) >= 0 ? 'pos' : 'neg'; }

async function refreshSummary(){
  const s = await get('/api/summary');
  const mode = (s.mode || 'paper').toUpperCase();
  document.getElementById('mode').textContent = mode;
  document.getElementById('mode').className = 'badge ' + (s.mode==='live' ? 'live' : 'paper');
  const p = s.portfolio || {};
  const ls = s.last_snapshot;
  document.getElementById('cash').textContent = fmt(p.cash);
  document.getElementById('equity').textContent = ls ? fmt(ls.equity) : (p.cash!=null ? fmt(p.cash) : '–');
  const pnl = p.realized_pnl || 0;
  const pnlEl = document.getElementById('pnl');
  pnlEl.textContent = fmt(pnl);
  pnlEl.className = 'value ' + pnlClass(pnl);
  document.getElementById('positions').textContent = (p.positions||[]).length;
  document.getElementById('fills').textContent = s.fills_count;
  document.getElementById('updated').textContent = 'updated ' + new Date().toLocaleTimeString();
}

async function refreshChart(){
  const series = await get('/api/equity');
  const svg = document.getElementById('chart');
  if(!series.length){ svg.innerHTML=''; return; }
  const w=600, h=180, pad=8;
  const vals = series.map(s=>s.equity);
  const min=Math.min(...vals), max=Math.max(...vals), range=(max-min)||1;
  const pts = series.map((s,i)=>{
    const x = pad + (i/(series.length-1))*(w-2*pad);
    const y = h-pad - ((s.equity-min)/range)*(h-2*pad);
    return x.toFixed(1)+','+y.toFixed(1);
  }).join(' ');
  svg.innerHTML = '<polyline points="'+pts+'" fill="none" stroke="#58a6ff" stroke-width="2"/>';
}

async function refreshFills(){
  const fills = await get('/api/fills?limit=50');
  const el = document.getElementById('fillsTable');
  if(!fills.length){ el.innerHTML='<div class="muted">No fills yet — run paper mode first.</div>'; return; }
  const rows = fills.slice().reverse().map(f=>
    '<tr><td>'+f.slug+'</td><td>'+f.outcome+'</td><td>'+f.action+'</td>'+
    '<td>'+Number(f.price).toFixed(3)+'</td><td>'+Number(f.qty).toFixed(2)+'</td>'+
    '<td>'+Number(f.notional).toFixed(2)+'</td></tr>').join('');
  el.innerHTML = '<table><tr><th>Market</th><th>Side</th><th>Action</th><th>Price</th>'+
                 '<th>Qty</th><th>Notional</th></tr>'+rows+'</table>';
}

async function loadMarkets(){
  const data = await get('/api/markets?limit=30');
  const el = document.getElementById('marketsTable');
  if(!Array.isArray(data)){ el.innerHTML='<div class="neg">'+(data.error||'error')+'</div>'; return; }
  const rows = data.map(m=>
    '<tr><td>'+m.question+'</td><td>'+m.status+'</td>'+
    '<td>'+(m.outcome_prices||[]).join(' / ')+'</td></tr>').join('');
  el.innerHTML = '<table><tr><th>Market</th><th>Status</th><th>Prices (Yes / No)</th></tr>'+rows+'</table>';
}

async function refreshStatus(){
  const s = await get('/api/status');
  const el = document.getElementById('botStatus');
  if(s.running){
    el.textContent = '● Running ('+(s.mode||'')+')';
    el.style.color = '#3fb950';
    document.getElementById('botDetail').textContent =
      'PID '+s.pid+' — stop loss $'+s.stop_loss+(s.started_at ? ' — since '+new Date(s.started_at*1000).toLocaleTimeString() : '');
  } else {
    el.textContent = '● Stopped';
    el.style.color = '#8b949e';
    document.getElementById('botDetail').textContent = '';
  }
}

async function startBot(){
  const mode = document.getElementById('modeSelect').value;
  const stopLoss = Number(document.getElementById('stopLoss').value) || 0;
  await fetch('/api/control/start', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({mode:mode, stop_loss:stopLoss})});
  await refreshStatus();
}

async function stopBot(){
  await fetch('/api/control/stop', {method:'POST'});
  await refreshStatus();
}

async function refreshLog(){
  const data = await get('/api/log?lines=100');
  document.getElementById('logBox').textContent = (data.length ? data.join('\\n') : '(no log yet)');
}

async function runBacktest(){
  const body = {
    limit: Number(document.getElementById('btLimit').value) || 10,
    lookback: Number(document.getElementById('btLookback').value) || 20,
    holding: Number(document.getElementById('btHolding').value) || 3,
    notional: Number(document.getElementById('btNotional').value) || 10,
  };
  const el = document.getElementById('btResults');
  el.textContent = 'Running…';
  const data = await post('/api/backtest', body);
  if(data.error){ el.innerHTML = '<span class="neg">'+data.error+'</span>'; return; }
  if(!data.results || !data.results.length){ el.textContent = 'No trades across the selected markets.'; return; }
  const rows = data.results.map(r=>
    '<tr><td>'+r.question+'</td><td>'+r.trades+'</td><td>'+(r.pnl>=0?'+':'')+r.pnl.toFixed(2)+'</td>'+
    '<td>'+Math.round(r.win_rate*100)+'%</td><td>'+r.max_drawdown.toFixed(2)+'</td></tr>').join('');
  el.innerHTML = '<table><tr><th>Market</th><th>Trades</th><th>P&amp;L</th><th>Win%</th><th>MaxDD</th></tr>'+
    rows+'</table><div style="margin-top:8px">TOTAL: '+data.total_trades+' trades, P&L '+
    (data.total_pnl>=0?'+':'')+data.total_pnl.toFixed(2)+'</div>';
}

async function saveKeys(){
  const el = document.getElementById('keysMsg');
  const body = {
    key_id: document.getElementById('keyId').value.trim(),
    secret_key: document.getElementById('secretKey').value.trim(),
    passphrase: document.getElementById('keyPass').value,
  };
  if(!body.key_id || !body.secret_key || !body.passphrase){ el.textContent = 'All three fields are required.'; return; }
  const data = await post('/api/set-keys', body);
  el.textContent = data.ok ? 'Keys saved (encrypted).' : ('Error: '+(data.error||''));
  if(data.ok){ ['keyId','secretKey','keyPass'].forEach(id=>document.getElementById(id).value=''); }
}

async function refreshAll(){
  await Promise.all([refreshSummary(), refreshChart(), refreshFills(), refreshStatus()]);
}
refreshAll();
setInterval(refreshAll, 5000);  // auto-refresh every 5 seconds
</script>
</body>
</html>
"""


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return True
    except OSError:
        return False


class BotController:
    """Starts/stops the bot as a subprocess so the dashboard can control it."""

    def __init__(self, data_dir: str, graceful_timeout: float = 15.0):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.state_path = os.path.join(data_dir, "control.json")
        self.log_path = os.path.join(data_dir, "bot.log")
        self.stop_file = os.path.abspath(os.path.join(data_dir, ".stop"))
        self.graceful_timeout = graceful_timeout
        self._proc: subprocess.Popen | None = None

    def start(self, mode: str = "paper", stop_loss: float = 20.0, command: list[str] | None = None) -> dict:
        if self.status()["running"]:
            return self.status()

        env = dict(os.environ)
        env["PM_MAX_DAILY_LOSS"] = str(stop_loss)
        env["PYTHONUNBUFFERED"] = "1"
        env["PM_STOP_FILE"] = self.stop_file
        self._remove_stop_file()
        if command is None:
            command = [sys.executable, "-m", "polymarket_bot.cli", mode]

        logf = open(self.log_path, "ab")
        self._proc = subprocess.Popen(
            command,
            cwd=os.getcwd(),
            env=env,
            stdout=logf,
            stderr=subprocess.STDOUT,
        )
        logf.close()
        self._write_state(
            {"pid": self._proc.pid, "mode": mode, "stop_loss": stop_loss, "started_at": time.time()}
        )
        return self.status()

    def stop(self) -> dict:
        # Request graceful stop via the stop file (works on Linux, macOS, Windows).
        try:
            with open(self.stop_file, "w") as f:
                f.write("stop")
        except OSError:
            pass

        if self._proc is not None:
            if self._proc.poll() is None:
                try:
                    self._proc.wait(timeout=self.graceful_timeout)
                except subprocess.TimeoutExpired:
                    self._proc.terminate()
                    try:
                        self._proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        self._proc.kill()
            self._proc = None

        state = self._read_state()
        if state and state.get("pid") and _pid_alive(state["pid"]):
            try:
                os.kill(state["pid"], signal.SIGTERM)
            except OSError:
                pass
        self._clear_state()
        self._remove_stop_file()
        return self.status()

    def _remove_stop_file(self) -> None:
        try:
            if os.path.exists(self.stop_file):
                os.remove(self.stop_file)
        except OSError:
            pass

    def status(self) -> dict:
        state = self._read_state()
        running = self._proc is not None and self._proc.poll() is None
        if state and state.get("pid"):
            running = running or _pid_alive(state["pid"])
        return {
            "running": running,
            "mode": (state or {}).get("mode"),
            "stop_loss": (state or {}).get("stop_loss"),
            "pid": (state or {}).get("pid"),
            "started_at": (state or {}).get("started_at"),
        }

    def _write_state(self, state: dict) -> None:
        with open(self.state_path, "w") as f:
            json.dump(state, f)

    def _read_state(self) -> dict:
        if not os.path.exists(self.state_path):
            return {}
        try:
            with open(self.state_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def _clear_state(self) -> None:
        if os.path.exists(self.state_path):
            os.remove(self.state_path)


class Dashboard:
    def __init__(self, config: Config):
        self.config = config
        self.client = PolymarketClient(config)
        self.controller = BotController(config.data_dir)

    def _read_jsonl(self, filename: str) -> list[dict]:
        path = os.path.join(self.config.data_dir, filename)
        if not os.path.exists(path):
            return []
        rows = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return rows

    def summary(self) -> dict:
        fills = self._read_jsonl("fills.jsonl")
        events = self._read_jsonl("events.jsonl")
        snapshots = [e for e in events if e.get("type") == "snapshot"]

        portfolio = {}
        portfolio_path = os.path.join(self.config.data_dir, "portfolio.json")
        if os.path.exists(portfolio_path):
            with open(portfolio_path) as f:
                portfolio = json.load(f)

        return {
            "mode": self.config.mode,
            "config": {
                "max_order_notional": self.config.max_order_notional,
                "max_position_notional": self.config.max_position_notional,
                "max_total_exposure": self.config.max_total_exposure,
                "max_daily_loss": self.config.max_daily_loss,
            },
            "portfolio": portfolio,
            "fills_count": len(fills),
            "last_snapshot": snapshots[-1] if snapshots else None,
        }

    def equity_series(self) -> list[dict]:
        events = self._read_jsonl("events.jsonl")
        return [e for e in events if e.get("type") == "snapshot"]

    def fills(self, limit: int = 200) -> list[dict]:
        rows = self._read_jsonl("fills.jsonl")
        return rows[-limit:]

    def markets(self, limit: int = 20):
        try:
            return [m.__dict__ for m in self.client.list_markets(closed=False, limit=limit)]
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    def log_tail(self, lines: int = 100) -> list[str]:
        if not os.path.exists(self.controller.log_path):
            return []
        with open(self.controller.log_path) as f:
            return f.read().splitlines()[-lines:]

    def run_backtest(self, limit=10, lookback=20, zscore=1.0, holding=3, notional=10.0, interval="INTERVAL_1H") -> dict:
        from .backtest import run_walk_forward

        fidelity = 1 if interval in ("INTERVAL_1H", "INTERVAL_6H", "INTERVAL_LIVE") else 5
        try:
            markets = self.client.list_markets(closed=False, limit=limit)
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc), "results": [], "total_pnl": 0, "total_trades": 0}

        results = []
        for m in markets:
            hist = self.client.get_price_history(m.slug, interval=interval, fidelity=fidelity)
            res = run_walk_forward(hist, lookback, zscore, holding, notional)
            if res.num_trades == 0:
                continue
            results.append(
                {
                    "slug": m.slug,
                    "question": m.question,
                    "trades": res.num_trades,
                    "pnl": round(res.total_pnl, 2),
                    "win_rate": round(res.win_rate, 4),
                    "max_drawdown": round(res.max_drawdown, 2),
                }
            )
        return {
            "results": results,
            "total_pnl": round(sum(r["pnl"] for r in results), 2),
            "total_trades": sum(r["trades"] for r in results),
        }

    def store_api_keys(self, key_id: str, secret_key: str, passphrase: str) -> None:
        from .secrets import store_keys

        store_keys(key_id, secret_key, passphrase)

    def shutdown(self) -> None:
        self.controller.stop()
        self.client.close()


class Handler(BaseHTTPRequestHandler):
    dashboard: Dashboard | None = None

    def _send(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, obj, status: int = 200) -> None:
        self._send(json.dumps(obj).encode(), "application/json", status)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            return {}

    def _check_auth(self) -> bool:
        return check_basic_auth(
            self.headers.get("Authorization", ""),
            self.dashboard.config.dashboard_password,
        )

    def _send_auth_required(self) -> None:
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Polymarket Bot"')
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if not self._check_auth():
            self._send_auth_required()
            return
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        d = self.dashboard

        if path == "/":
            self._send(PAGE.encode(), "text/html; charset=utf-8")
        elif path == "/api/summary":
            self._send_json(d.summary())
        elif path == "/api/equity":
            self._send_json(d.equity_series())
        elif path == "/api/fills":
            self._send_json(d.fills(int(qs.get("limit", ["200"])[0])))
        elif path == "/api/markets":
            self._send_json(d.markets(int(qs.get("limit", ["20"])[0])))
        elif path == "/api/status":
            self._send_json(d.controller.status())
        elif path == "/api/log":
            self._send_json(d.log_tail(int(qs.get("lines", ["100"])[0])))
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self) -> None:  # noqa: N802
        if not self._check_auth():
            self._send_auth_required()
            return
        parsed = urlparse(self.path)
        path = parsed.path
        d = self.dashboard
        body = self._read_body()

        if path == "/api/control/start":
            mode = body.get("mode", "paper")
            if mode not in ("paper", "live"):
                self._send_json({"error": "mode must be paper or live"}, 400)
                return
            stop_loss = float(body.get("stop_loss", self.dashboard.config.max_daily_loss))
            self._send_json(d.controller.start(mode, stop_loss))
        elif path == "/api/control/stop":
            self._send_json(d.controller.stop())
        elif path == "/api/backtest":
            self._send_json(
                d.run_backtest(
                    limit=int(body.get("limit", 10)),
                    lookback=int(body.get("lookback", 20)),
                    zscore=float(body.get("zscore", 1.0)),
                    holding=int(body.get("holding", 3)),
                    notional=float(body.get("notional", 10.0)),
                )
            )
        elif path == "/api/set-keys":
            try:
                d.store_api_keys(body.get("key_id", ""), body.get("secret_key", ""), body.get("passphrase", ""))
                self._send_json({"ok": True})
            except Exception as exc:  # noqa: BLE001
                self._send_json({"ok": False, "error": str(exc)})
        else:
            self._send_json({"error": "not found"}, 404)

    def log_message(self, *args) -> None:
        pass


def run_server(config: Config, host: str = "127.0.0.1", port: int = 8000) -> None:
    Handler.dashboard = Dashboard(config)
    server = ThreadingHTTPServer((host, port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if Handler.dashboard is not None:
            Handler.dashboard.shutdown()

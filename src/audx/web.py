"""Read-only HTTP companion (spec §11 `audx serve`).

Localhost-only by default. Renders a tiny dashboard that polls /state so a
phone can monitor transport + levels while wandering the room.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from audx.engine import get_engine
from audx.pattern import get_pattern_engine

DASHBOARD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>audx · monitor</title>
<style>
  :root { color-scheme: dark; }
  body { font: 14px/1.5 ui-monospace, monospace; background: #08070a; color: #e8dccb; margin: 0; padding: 24px; }
  h1 { color: #d4a574; font-size: 14px; letter-spacing: .14em; text-transform: uppercase; margin: 0 0 16px; }
  .row { display: flex; gap: 12px; margin-bottom: 6px; align-items: center; }
  .name { width: 110px; color: #7a6e5d; }
  .bar { background: #14111a; height: 12px; flex: 1; border: 1px solid #2a2330; position: relative; }
  .fill { background: #d4a574; height: 100%; width: 0; transition: width .08s linear; }
  .meta { color: #7a6e5d; font-size: 11px; letter-spacing: .12em; text-transform: uppercase; margin-top: 24px; }
</style>
</head>
<body>
<h1>audx · read-only</h1>
<div id="head"></div>
<div id="rows"></div>
<div class="meta">refreshes every 200 ms · localhost-only · spec §11</div>
<script>
const fmt = v => String(v).padStart(3, ' ');
async function tick() {
  try {
    const r = await fetch('/state');
    const s = await r.json();
    document.getElementById('head').textContent =
      `${s.playing ? '▶' : '■'}  ${fmt(s.bpm.toFixed(1))} bpm  ·  bar ${fmt(s.bar+1)}  ·  beat ${fmt(s.beat.toFixed(2))}`;
    const rows = document.getElementById('rows');
    rows.innerHTML = s.levels.map((lvl, i) =>
      `<div class="row"><span class="name">ch ${String(i+1).padStart(2,'0')}</span><div class="bar"><div class="fill" style="width:${Math.min(100, lvl*100).toFixed(1)}%"></div></div></div>`
    ).join('');
  } catch (_) {}
  setTimeout(tick, 200);
}
tick();
</script>
</body>
</html>
"""


def _state() -> dict:
    pe = get_pattern_engine()
    engine = get_engine()
    levels: list[float] = list(engine.get_channel_levels()) if engine else []
    return {
        "bpm": float(pe.bpm),
        "bar": int(pe.current_bar),
        "beat": float(pe.current_beat),
        "playing": bool(pe.running),
        "levels": [float(level) for level in levels],
        "patterns": [
            {"name": name, "dsl": pattern.dsl, "channel": pattern.channel}
            for name, pattern in pe.patterns.items()
        ],
    }


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            body = DASHBOARD.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/state":
            body = json.dumps(_state()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def log_message(self, *args: object) -> None:  # silence default access logs
        return


def serve(host: str = "127.0.0.1", port: int = 8080) -> None:
    """Serve the dashboard until KeyboardInterrupt."""
    httpd = ThreadingHTTPServer((host, port), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        thread.join()
    except KeyboardInterrupt:
        httpd.shutdown()

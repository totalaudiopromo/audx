"""Read-only HTTP companion (spec §11 `audx serve`).

Localhost-only by default. Renders a live dashboard — a step-sequencer grid with a
moving playhead plus channel meters — that polls ``/state``, so a phone or a second
screen can watch the session while audx runs in the terminal. Pure stdlib.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from audx.engine import get_engine
from audx.pattern import get_pattern_engine

STEPS_PER_BAR = 16

DASHBOARD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>audx · monitor</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { font: 14px/1.5 ui-monospace,"JetBrains Mono",monospace; background:#0a0a0a; color:#ececea; margin:0; padding:32px; }
  .frame { max-width: 1000px; margin: 0 auto; border: 1px solid #23231f; padding: 28px 32px; }
  header { display:flex; justify-content:space-between; align-items:baseline; color:#9a9a95; letter-spacing:2px; margin-bottom:24px; }
  header .wm { color:#9a9a95; }
  header .tp { color:#56554f; }
  .accent { color:#d79a4e; }
  .grid { display:flex; flex-direction:column; gap:8px; margin-bottom:28px; }
  .trk { display:flex; align-items:center; height:34px; }
  .lbl { width:120px; text-align:right; padding-right:18px; color:#9a9a95; }
  .cells { display:flex; gap:6px; position:relative; }
  .cell { width:34px; height:34px; border-radius:3px; box-shadow: inset 0 0 0 1px #1f1f1c; }
  .cell.beat { box-shadow: inset 0 0 0 1px #2e2e29; }
  .cell.on { background:#ececea; box-shadow:none; }
  .cell.cur { background:#d79a4e; }
  .vu { width:90px; height:8px; margin-left:18px; background:#16160f; border:1px solid #23231f; }
  .vu > div { height:100%; background:#d79a4e; width:0; transition:width .08s linear; }
  .meta { color:#56554f; font-size:11px; letter-spacing:1px; margin-top:8px; }
  .empty { color:#56554f; padding: 20px 0; }
</style>
</head>
<body>
<div class="frame">
  <header>
    <span class="wm">audx · monitor</span>
    <span id="transport" class="tp"></span>
  </header>
  <div id="grid" class="grid"></div>
  <div id="empty" class="empty" hidden>no patterns loaded — try <span class="accent">audx open</span></div>
  <div class="meta">read-only · localhost · refreshes 10x/s</div>
</div>
<script>
const N = 16;
function render(s) {
  document.getElementById('transport').innerHTML =
    (s.playing ? '▶' : '■') + '  ' + s.bpm.toFixed(1) + ' bpm · bar ' + (s.bar+1) +
    ' · beat ' + s.beat.toFixed(2);
  const grid = document.getElementById('grid');
  const empty = document.getElementById('empty');
  empty.hidden = s.tracks.length > 0;
  const cur = Math.floor(s.step) % N;
  grid.innerHTML = s.tracks.map((t) => {
    const cells = t.steps.map((on, i) => {
      const cls = ['cell'];
      if (i % 4 === 0) cls.push('beat');
      if (on) cls.push('on');
      if (on && i === cur && s.playing) cls.push('cur');
      return '<div class="'+cls.join(' ')+'"></div>';
    }).join('');
    const lvl = Math.min(100, (s.levels[t.channel]||0)*100).toFixed(1);
    return '<div class="trk"><span class="lbl">'+t.name+'</span>'+
           '<div class="cells">'+cells+'</div>'+
           '<div class="vu"><div style="width:'+lvl+'%"></div></div></div>';
  }).join('');
}
async function tick(){
  try { const r = await fetch('/state'); render(await r.json()); } catch(_) {}
  setTimeout(tick, 100);
}
tick();
</script>
</body>
</html>
"""


def _step_grid(pattern: object) -> list[int]:
    grid = [0] * STEPS_PER_BAR
    for step in getattr(pattern, "steps", []):
        idx = round(step.beat * 4) % STEPS_PER_BAR
        grid[idx] = 1
    return grid


def _state() -> dict:
    pe = get_pattern_engine()
    engine = get_engine()
    levels: list[float] = list(engine.get_channel_levels()) if engine else []
    return {
        "bpm": float(pe.bpm),
        "bar": int(pe.current_bar),
        "beat": float(pe.current_beat),
        "step": float(pe.current_beat * 4.0),
        "playing": bool(pe.running),
        "levels": [float(level) for level in levels],
        "tracks": [
            {"name": name, "channel": int(pattern.channel), "steps": _step_grid(pattern)}
            for name, pattern in pe.patterns.items()
        ],
    }


class _Handler(BaseHTTPRequestHandler):
    def _send(self, body: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self._send(DASHBOARD.encode("utf-8"), "text/html; charset=utf-8")
            return
        if self.path == "/state":
            self._send(json.dumps(_state()).encode("utf-8"), "application/json")
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

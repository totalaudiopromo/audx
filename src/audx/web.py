"""Local HTTP companion and browser instrument for `audx serve`.

Localhost-only by default. Exposes the original monitor dashboard plus a
playable Web Audio UI at /app for loading and auditioning audx projects.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from audx.engine import get_engine
from audx.pattern import get_pattern_engine
from audx.project import Project

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

BROWSER_APP = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>audx browser</title>
<style>
  :root { color-scheme: dark; --bg:#08070a; --panel:#14111a; --line:#2a2330; --fg:#e8dccb; --muted:#7a6e5d; --accent:#d4a574; --ok:#7fb069; }
  * { box-sizing: border-box; }
  body { margin:0; min-height:100vh; background: radial-gradient(900px 520px at 80% -10%, rgba(212,165,116,.08), transparent 62%), var(--bg); color:var(--fg); font: 13px/1.45 ui-monospace, SFMono-Regular, Menlo, monospace; }
  main { max-width:1180px; margin:0 auto; padding:28px; }
  header { display:flex; justify-content:space-between; align-items:baseline; border-bottom:1px solid var(--line); padding-bottom:14px; margin-bottom:18px; }
  h1 { margin:0; font-size:22px; color:var(--accent); letter-spacing:.08em; }
  button, input { font:inherit; }
  button { background:var(--panel); color:var(--fg); border:1px solid var(--line); padding:8px 12px; cursor:pointer; }
  button:hover { border-color:var(--accent); color:var(--accent); }
  .transport { display:flex; gap:8px; align-items:center; margin:18px 0; }
  .grid { display:grid; grid-template-columns: 220px repeat(16, 1fr); gap:4px; align-items:center; }
  .cell { min-height:28px; border:1px solid var(--line); background:#0e0c10; display:grid; place-items:center; }
  .hit { background:rgba(212,165,116,.22); color:var(--accent); border-color:rgba(212,165,116,.55); }
  .now { outline:2px solid var(--ok); outline-offset:-2px; }
  .track { justify-content:start; padding:0 10px; color:var(--fg); }
  .meter { height:6px; background:#0e0c10; border:1px solid var(--line); margin-top:4px; }
  .fill { width:0%; height:100%; background:var(--ok); }
  .drop { border:1px dashed var(--line); padding:16px; color:var(--muted); margin-top:18px; }
  .status { color:var(--muted); margin-top:14px; }
</style>
</head>
<body>
<main>
  <header><h1>audx browser</h1><div id="meta">local · Web Audio · no cloud</div></header>
  <div class="transport">
    <button id="play">▶ play</button>
    <button id="stop">■ stop</button>
    <span id="clock">000.0 bpm · bar 001:01</span>
  </div>
  <section id="grid" class="grid"></section>
  <div class="drop"><input id="files" type="file" accept="audio/*" multiple /> Load local samples into the browser session</div>
  <div class="status" id="status">ready</div>
</main>
<script>
const params = new URLSearchParams(location.search);
const projectPath = params.get('project') || 'project.audx';
const state = { project:null, ctx:null, buffers:new Map(), playing:false, step:0, timer:null, bpm:128 };

function parseGrid(dsl) {
  const m = dsl.match(/\\[([^\\]]+)\\]/);
  if (m) return [...m[1]].filter(ch => '10xX.-'.includes(ch)).map(ch => ch === '1' || ch.toLowerCase() === 'x');
  if (dsl.includes('4/4')) return [1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0].map(Boolean);
  if (dsl.includes('2/8')) return [0,0,0,0,1,0,0,0,0,0,0,0,1,0,0,0].map(Boolean);
  if (dsl.includes('16x8')) return [1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0].map(Boolean);
  return [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0].map(Boolean);
}

function render() {
  const grid = document.getElementById('grid');
  const patterns = state.project?.patterns || [];
  grid.innerHTML = '<div></div>' + Array.from({length:16}, (_,i)=>`<div class="cell">${String(i+1).padStart(2,'0')}</div>`).join('');
  patterns.forEach((p, row) => {
    const cells = parseGrid(p.dsl);
    grid.insertAdjacentHTML('beforeend', `<div class="cell track">${p.name}<div class="meter"><div class="fill" id="m${row}"></div></div></div>`);
    cells.forEach((on, i) => grid.insertAdjacentHTML('beforeend', `<button class="cell ${on ? 'hit' : ''}" data-row="${row}" data-step="${i}">${on ? '█' : '·'}</button>`));
  });
}

async function ensureAudio() {
  if (!state.ctx) state.ctx = new AudioContext();
  if (state.ctx.state === 'suspended') await state.ctx.resume();
}

async function loadProject() {
  const res = await fetch('/api/project?path=' + encodeURIComponent(projectPath));
  state.project = await res.json();
  state.bpm = state.project.bpm || 128;
  document.getElementById('meta').textContent = `${state.project.name} · ${state.bpm.toFixed(1)} bpm`;
  render();
  for (const row of state.project.mixer || []) {
    if (row.sample) {
      try {
        const audio = await fetch('/api/audio?path=' + encodeURIComponent((state.project.root + '/' + row.sample))).then(r => r.arrayBuffer());
        state.buffers.set(row.sample, await (state.ctx || new AudioContext()).decodeAudioData(audio.slice(0)));
      } catch (err) {
        console.warn('sample load failed', row.sample, err);
      }
    }
  }
}

function trigger(pattern, rowIndex) {
  const mixer = (state.project.mixer || []).find(row => row.channel === pattern.channel);
  const key = mixer?.sample;
  const buffer = key ? state.buffers.get(key) : null;
  const gainValue = Math.max(0, Math.min(1.2, 0.75 * Math.pow(10, ((mixer?.gain_db || 0) / 20))));
  const panValue = Math.max(-1, Math.min(1, mixer?.pan || 0));
  if (!state.ctx) return;
  if (buffer) {
    const src = state.ctx.createBufferSource();
    const gain = state.ctx.createGain();
    const pan = state.ctx.createStereoPanner();
    gain.gain.value = gainValue;
    src.buffer = buffer;
    pan.pan.value = panValue;
    src.connect(gain).connect(pan).connect(state.ctx.destination);
    src.start();
  } else {
    const osc = state.ctx.createOscillator();
    const gain = state.ctx.createGain();
    const pan = state.ctx.createStereoPanner();
    osc.frequency.value = rowIndex === 0 ? 72 : 220 + rowIndex * 40;
    pan.pan.value = panValue;
    gain.gain.setValueAtTime(0.14 * gainValue, state.ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, state.ctx.currentTime + 0.12);
    osc.connect(gain).connect(pan).connect(state.ctx.destination);
    osc.start();
    osc.stop(state.ctx.currentTime + 0.13);
  }
}

async function play() {
  await ensureAudio();
  state.playing = true;
  const interval = (60 / state.bpm / 4) * 1000;
  clearInterval(state.timer);
    state.timer = setInterval(() => {
    document.querySelectorAll('.now').forEach(el => el.classList.remove('now'));
    document.querySelectorAll(`[data-step="${state.step}"]`).forEach(el => el.classList.add('now'));
    (state.project.patterns || []).forEach((pattern, row) => {
      if (parseGrid(pattern.dsl)[state.step]) trigger(pattern, row);
      const meter = document.getElementById('m' + row);
      if (meter) { meter.style.width = parseGrid(pattern.dsl)[state.step] ? '90%' : '8%'; setTimeout(()=>meter.style.width='0%', 90); }
    });
    document.getElementById('clock').textContent = `${state.bpm.toFixed(1).padStart(5,'0')} bpm · step ${String(state.step+1).padStart(2,'0')}`;
    state.step = (state.step + 1) % 16;
  }, interval);
}

function stop() { state.playing = false; clearInterval(state.timer); state.step = 0; }
document.getElementById('play').onclick = play;
document.getElementById('stop').onclick = stop;
document.getElementById('files').onchange = async (event) => {
  await ensureAudio();
  for (const file of event.target.files) {
    const audio = await file.arrayBuffer();
    state.buffers.set(file.name, await state.ctx.decodeAudioData(audio));
  }
  document.getElementById('status').textContent = `loaded ${event.target.files.length} browser file(s)`;
};
loadProject().catch(err => document.getElementById('status').textContent = String(err));
</script>
</body>
</html>
"""


def _state() -> dict[str, Any]:
    pe = get_pattern_engine()
    engine = get_engine()
    levels: list[float] = [float(level) for level in engine.get_channel_levels()] if engine else []
    return {
        "bpm": float(pe.bpm),
        "bar": int(pe.current_bar),
        "beat": float(pe.current_beat),
        "playing": bool(pe.running),
        "levels": levels,
        "patterns": [
            {"name": name, "dsl": pattern.dsl, "channel": pattern.channel}
            for name, pattern in pe.patterns.items()
        ],
    }


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            body = DASHBOARD.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/app":
            body = BROWSER_APP.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/api/project":
            params = parse_qs(parsed.query)
            project_path = Path(params.get("path", ["project.audx"])[0]).expanduser()
            if not project_path.exists():
                self.send_error(404, "project not found")
                return
            project = Project.load(project_path)
            payload = {
                "root": str(project_path.parent),
                "name": project.name,
                "bpm": project.bpm,
                "time_sig": project.time_sig,
                "patterns": project.patterns,
                "mixer": project.mixer,
            }
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/api/audio":
            params = parse_qs(parsed.query)
            audio_path = Path(params.get("path", [""])[0]).expanduser()
            if not audio_path.exists() or not audio_path.is_file():
                self.send_error(404, "audio not found")
                return
            body = audio_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/state":
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

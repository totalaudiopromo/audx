#!/usr/bin/env python3
"""Render static audx UI previews as SVG files.

These are honest visual direction mocks derived from the current Textual layout:
compact mixer, pattern row, transport, CLI/daemon screens.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

OUT = Path("/tmp/audx-ui-previews")
OUT.mkdir(parents=True, exist_ok=True)

BG = "#111111"
SURFACE = "#1e1e1e"
SURFACE_2 = "#161616"
BORDER = "#333333"
TEXT = "#e0e0e0"
MUTED = "#888888"
AMBER = "#d4a574"
SAGE = "#a8c087"
PINK = "#e8a6c2"
RED = "#c97064"


def esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x: int, y: int, body: str, *, size: int = 14, fill: str = TEXT, weight: str = "400") -> str:
    return f'<text x="{x}" y="{y}" font-family="JetBrains Mono, SF Mono, Menlo, monospace" font-size="{size}" font-weight="{weight}" fill="{fill}">{esc(body)}</text>'


def rect(x: int, y: int, w: int, h: int, *, fill: str = SURFACE, stroke: str = BORDER, rx: int = 0) -> str:
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="1" />'


def button(x: int, y: int, w: int, h: int, label: str, *, fill: str = SURFACE_2, stroke: str = BORDER, fg: str = TEXT) -> str:
    return rect(x, y, w, h, fill=fill, stroke=stroke, rx=4) + text(x + 10, y + 20, label, size=13, fill=fg, weight="600")


def frame(title: str, subtitle: str, inner: str, filename: str, w: int = 1280, h: int = 760) -> Path:
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
  <rect width="100%" height="100%" fill="{BG}" />
  {rect(24, 24, w-48, 44, fill=SURFACE, stroke=BORDER)}
  {text(44, 53, title, size=18, fill=AMBER, weight="700")}
  {text(w-320, 53, subtitle, size=13, fill=MUTED)}
  {inner}
</svg>'''
    path = OUT / filename
    path.write_text(svg)
    return path


def mixer_screen() -> Path:
    parts = []
    parts.append(rect(24, 84, 1232, 500, fill=BG, stroke="none"))
    x0, y0 = 44, 105
    strip_w, gap = 62, 13
    levels = [0.88, 0.12, 0.74, 0.55, 0.0, 0.36, 0.22, 0.68, 0.0, 0.18, 0.44, 0.04, 0.62, 0.26, 0.08, 0.0]
    muted = {5, 9, 16}
    for i in range(16):
        x = x0 + i * (strip_w + gap)
        parts.append(rect(x, y0, strip_w, 450, fill=SURFACE, stroke=BORDER))
        parts.append(text(x + 19, y0 + 26, f"{i+1:02d}", size=14, fill=AMBER, weight="700"))
        meter_h = 140
        parts.append(rect(x + 22, y0 + 48, 18, meter_h, fill="#0d0d0d", stroke="#292929"))
        fill_h = int(meter_h * levels[i])
        parts.append(f'<rect x="{x+23}" y="{y0+48+meter_h-fill_h}" width="16" height="{fill_h}" fill="{SAGE}" opacity="0.9"/>')
        parts.append(text(x + 10, y0 + 214, "gain", size=10, fill=MUTED))
        parts.append(text(x + 12, y0 + 234, "1.00", size=12, fill=TEXT))
        parts.append(button(x + 8, y0 + 252, 20, 26, "-", fg=MUTED))
        parts.append(button(x + 34, y0 + 252, 20, 26, "+", fg=MUTED))
        mfill = RED if i + 1 in muted else SURFACE_2
        mfg = "#1b1111" if i + 1 in muted else MUTED
        parts.append(button(x + 7, y0 + 302, 48, 28, "Mute", fill=mfill, fg=mfg))
        parts.append(text(x + 16, y0 + 410, "░░░", size=11, fill="#454545"))
    parts.append(rect(24, 596, 1232, 70, fill=SURFACE_2, stroke=BORDER))
    parts.append(text(44, 624, "patterns", size=13, fill=MUTED))
    parts.append(button(130, 608, 100, 34, "kick", fill="#1f2a1f", stroke=SAGE, fg=SAGE))
    parts.append(button(242, 608, 100, 34, "hats", fill="#1f2a1f", stroke=SAGE, fg=SAGE))
    parts.append(button(354, 608, 100, 34, "snare", fill=SURFACE_2, stroke=BORDER, fg=MUTED))
    parts.append(rect(24, 682, 1232, 50, fill=SURFACE, stroke=BORDER))
    parts.append(button(44, 692, 42, 30, "▶", fill="#172417", stroke=SAGE, fg=SAGE))
    parts.append(button(96, 692, 42, 30, "■", fill="#2a1818", stroke=RED, fg=RED))
    parts.append(text(168, 713, "BPM 128", size=15, fill=TEXT, weight="700"))
    parts.append(button(260, 692, 58, 30, "tap", fill="#1b2024", stroke=AMBER, fg=AMBER))
    parts.append(text(1040, 713, "space play/stop · 1-9 mute", size=12, fill=MUTED))
    return frame("audx", "launch · mixer", "\n".join(parts), "01-launch-mixer.svg")


def pattern_screen() -> Path:
    parts = []
    parts.append(rect(70, 110, 1140, 210, fill=SURFACE, stroke=BORDER))
    lines = [
        "$ audx pattern create hats 'hh 16x8 | swing 50% | vel 0.45 | channel 2'",
        "Pattern 'hats' created (16 steps)",
        "  beat 0.00: hihat vel=0.45 ch=2",
        "  beat 0.25 → 0.375 swung: hihat vel=0.45 ch=2",
        "  beat 0.50: hihat vel=0.45 ch=2",
        "  …",
    ]
    y = 145
    for i, line in enumerate(lines):
        parts.append(text(100, y + i * 28, line, size=15, fill=AMBER if i == 0 else TEXT))
    parts.append(rect(70, 360, 1140, 230, fill=SURFACE_2, stroke=BORDER))
    parts.append(text(100, 395, "Pattern grid", size=16, fill=AMBER, weight="700"))
    grid_x, grid_y = 100, 430
    for i in range(16):
        x = grid_x + i * 62
        fill = SAGE if i % 2 == 0 else "#304830"
        parts.append(rect(x, grid_y, 44, 44, fill=fill, stroke="#5d6b4f", rx=4))
        parts.append(text(x + 14, grid_y + 28, "x", size=16, fill="#101510", weight="700"))
        parts.append(text(x + 2, grid_y + 68, f"{i/4:.2f}", size=10, fill=MUTED))
    parts.append(text(100, 548, "Swing view: odd 16ths drift right, not just metadata", size=14, fill=MUTED))
    return frame("audx", "pattern create", "\n".join(parts), "02-pattern-create.svg")


def render_screen() -> Path:
    parts = []
    parts.append(rect(64, 110, 1150, 165, fill=SURFACE, stroke=BORDER))
    lines = [
        "$ audx render 'kick 4/4' --sample ~/Samples/kick.wav --output render.wav --bars 4",
        "Indexed 1 sample under ~/Samples",
        "Rendered render.wav",
    ]
    for i, line in enumerate(lines):
        parts.append(text(96, 150 + i * 32, line, size=15, fill=AMBER if i == 0 else TEXT))
    parts.append(rect(64, 320, 1150, 260, fill=SURFACE_2, stroke=BORDER))
    parts.append(text(96, 358, "Offline render preview", size=16, fill=AMBER, weight="700"))
    # waveform
    base_y = 465
    for i in range(120):
        x = 100 + i * 8
        amp = int((20 + (i % 8) * 8) * (1 if i % 16 < 5 else 0.25))
        col = SAGE if i % 16 < 5 else "#2d3a2d"
        parts.append(f'<line x1="{x}" y1="{base_y-amp}" x2="{x}" y2="{base_y+amp}" stroke="{col}" stroke-width="3"/>')
    parts.append(text(96, 550, "Result: stereo WAV, normalised if peak > 1.0", size=13, fill=MUTED))
    return frame("audx", "render", "\n".join(parts), "03-render.svg")


def plugins_screen() -> Path:
    parts = []
    parts.append(rect(64, 100, 1150, 540, fill=SURFACE, stroke=BORDER))
    rows = [
        ("AU", "Analog Lab V", "/Library/Audio/Plug-Ins/Components/Analog Lab V.component"),
        ("AU", "Arcade", "/Library/Audio/Plug-Ins/Components/Arcade.component"),
        ("AU", "Atlas", "/Library/Audio/Plug-Ins/Components/Atlas.component"),
        ("VST3", "ValhallaVintageVerb", "~/Library/Audio/Plug-Ins/VST3/ValhallaVintageVerb.vst3"),
        ("VST3", "SketchCassette", "~/Library/Audio/Plug-Ins/VST3/SketchCassette.vst3"),
    ]
    parts.append(text(92, 140, "$ audx plugins scan", size=15, fill=AMBER))
    y = 190
    parts.append(text(92, y, "type", size=12, fill=MUTED))
    parts.append(text(180, y, "name", size=12, fill=MUTED))
    parts.append(text(430, y, "path", size=12, fill=MUTED))
    y += 30
    for kind, name, path in rows:
        parts.append(text(92, y, kind, size=14, fill=PINK if kind == "VST3" else SAGE, weight="700"))
        parts.append(text(180, y, name, size=14, fill=TEXT))
        parts.append(text(430, y, path, size=12, fill=MUTED))
        y += 36
    parts.append(text(92, 585, "Discovery only. Hosting requires the next audio-safe plugin bridge.", size=13, fill=RED))
    return frame("audx", "plugins", "\n".join(parts), "04-plugins.svg")


def daemon_screen() -> Path:
    parts = []
    parts.append(rect(64, 105, 1150, 500, fill=SURFACE, stroke=BORDER))
    lines = [
        "$ audx daemon serve --port 5744",
        "audxd listening on http://127.0.0.1:5744",
        "",
        "$ audx daemon status",
        "{'ok': True, 'bpm': 120.0, 'patterns': []}",
        "$ audx daemon pattern demo 'kick 4/4'",
        "{'ok': True, 'steps': 4}",
        "$ audx daemon save /tmp/audx-daemon-test.audx",
        "{'ok': True, 'path': '/tmp/audx-daemon-test.audx'}",
    ]
    y = 145
    for line in lines:
        fill = AMBER if line.startswith("$") else SAGE if line.startswith("{") else TEXT
        parts.append(text(96, y, line, size=15, fill=fill))
        y += 34 if line else 18
    parts.append(text(96, 565, "State persists while audxd is alive. Not yet the production audio daemon.", size=13, fill=MUTED))
    return frame("audx", "daemon", "\n".join(parts), "05-daemon.svg")


def bridges_screen() -> Path:
    parts = []
    parts.append(rect(64, 105, 1150, 500, fill=SURFACE, stroke=BORDER))
    rows = [
        ("push2 map", "play note 85 · stop note 86 · encoders cc 14-17", SAGE),
        ("heartmula status", "available: heartlib bridge available", SAGE),
        ("sadact status", "unavailable: localhost:5742 connection refused", RED),
    ]
    y = 150
    for title, detail, colour in rows:
        parts.append(rect(92, y - 26, 1080, 72, fill=SURFACE_2, stroke=BORDER, rx=6))
        parts.append(text(116, y, f"$ audx {title}", size=15, fill=AMBER))
        parts.append(text(116, y + 28, detail, size=14, fill=colour))
        y += 105
    parts.append(text(116, 540, "Bridge screens should feel operational, not magical. Green means wired. Red means blocked.", size=13, fill=MUTED))
    return frame("audx", "bridges", "\n".join(parts), "06-bridges.svg")


if __name__ == "__main__":
    paths = [mixer_screen(), pattern_screen(), render_screen(), plugins_screen(), daemon_screen(), bridges_screen()]
    for path in paths:
        print(path)

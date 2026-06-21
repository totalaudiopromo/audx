#!/usr/bin/env python3
"""Generate an animated terminal GIF of an `audx` session for the README.

Pure Pillow — no ffmpeg, no browser. Renders a fake-but-faithful terminal
window typing out an audx session in the app's warm palette, then writes an
optimized looping GIF to docs/assets/audx-demo.gif.

Run:  uv run --with pillow python scripts/make-demo-gif.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ── palette (matches src/audx/config.py THEME) ────────────────────────────────
BG = (17, 17, 17)
SURFACE = (30, 30, 30)
BAR = (24, 24, 24)
TEXT = (224, 224, 224)
MUTED = (136, 136, 136)
AMBER = (212, 165, 116)
SAGE = (168, 192, 135)
PINK = (232, 166, 194)
RED = (255, 95, 86)

FONT_DIR = Path("/mnt/skills/examples/canvas-design/canvas-fonts")
FONT = ImageFont.truetype(str(FONT_DIR / "JetBrainsMono-Regular.ttf"), 22)
FONT_BOLD = ImageFont.truetype(str(FONT_DIR / "JetBrainsMono-Bold.ttf"), 22)

W, H = 900, 560
PAD = 28
LINE_H = 30
TOP = 70  # below the title bar

# Each "line" is a list of (text, color, bold) segments. None = blank line.
Seg = tuple[str, tuple[int, int, int], bool]
SCRIPT: list[list[Seg] | None] = [
    [("$ ", PINK, True), ("pip install audx", TEXT, True)],
    [("Successfully installed audx-0.3.0", MUTED, False)],
    None,
    [("$ ", PINK, True), ("audx demo loop.wav", TEXT, True)],
    [("  audx · demo", AMBER, True)],
    [("    ♪ kick     kick 4/4", MUTED, False)],
    [("    ♪ sub      sub e(3,8) | tune -5st", MUTED, False)],
    [("    ♪ clap     clap 2/8", MUTED, False)],
    [("    ♪ hats     hh 16x8 | swing 12%", MUTED, False)],
    [("    ♪ bass     bass e(3,8) | tune -7st", MUTED, False)],
    [("  ✓ rendered 4 bars @ 124 BPM → loop.wav", SAGE, True)],
    None,
    [("$ ", PINK, True), ('audx render "cowbell e(5,16,2)"', TEXT, True)],
    [("Rendered render.wav", SAGE, False)],
    None,
    [("$ ", PINK, True), ("# code your music. own your sound.", AMBER, False)],
]


def draw_window(visible_lines: list[list[Seg] | None], cursor: bool) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # window body + title bar
    d.rounded_rectangle([10, 10, W - 10, H - 10], radius=14, fill=SURFACE)
    d.rounded_rectangle([10, 10, W - 10, 50], radius=14, fill=BAR)
    d.rectangle([10, 38, W - 10, 50], fill=BAR)
    for i, col in enumerate((RED, AMBER, SAGE)):
        d.ellipse([34 + i * 26, 23, 48 + i * 26, 37], fill=col)
    title = "audx — make a beat in 10 seconds"
    tw = d.textlength(title, font=FONT)
    d.text(((W - tw) / 2, 18), title, font=FONT, fill=MUTED)

    y = TOP
    for line in visible_lines:
        if line is not None:
            x = PAD
            for text, color, bold in line:
                f = FONT_BOLD if bold else FONT
                d.text((x, y), text, font=f, fill=color)
                x += d.textlength(text, font=f)
        y += LINE_H

    if cursor and visible_lines:
        last = visible_lines[-1]
        x = PAD
        if last is not None:
            for text, _, bold in last:
                x += d.textlength(text, font=FONT_BOLD if bold else FONT)
        cy = TOP + (len(visible_lines) - 1) * LINE_H
        d.rectangle([x + 2, cy + 2, x + 13, cy + 24], fill=AMBER)
    return img


def main() -> None:
    frames: list[Image.Image] = []
    durations: list[int] = []
    shown: list[list[Seg] | None] = []

    for line in SCRIPT:
        if line is None:
            shown.append(None)
            frames.append(draw_window(shown, cursor=False))
            durations.append(120)
            continue
        # type the line in progressively (segment by segment for speed/clarity)
        partial: list[Seg] = []
        shown.append(partial)
        full_text = "".join(seg[0] for seg in line)
        built = ""
        # character-stagger the merged text but keep segment colours
        for seg in line:
            text, color, bold = seg
            step = max(1, len(text) // 8)
            for i in range(step, len(text) + 1, step):
                shown[-1] = _slice_segments(line, built + text[:i])
                frames.append(draw_window(shown, cursor=True))
                durations.append(45)
            built += text
        shown[-1] = list(line)
        frames.append(draw_window(shown, cursor=True))
        durations.append(420 if full_text.startswith("$") else 160)

    # hold the final frame
    frames.append(draw_window(shown, cursor=True))
    durations.append(2200)

    out = Path("docs/assets/audx-demo.gif")
    out.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        out,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(f"wrote {out} ({len(frames)} frames, {out.stat().st_size // 1024} KB)")


def _slice_segments(line: list[Seg], upto: str) -> list[Seg]:
    """Return segments truncated so their concatenation equals ``upto``."""
    result: list[Seg] = []
    remaining = len(upto)
    for text, color, bold in line:
        if remaining <= 0:
            break
        take = min(len(text), remaining)
        result.append((text[:take], color, bold))
        remaining -= take
    return result


if __name__ == "__main__":
    main()

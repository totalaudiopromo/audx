#!/usr/bin/env python3
"""Build the promo beat + a frame-accurate data track for the Remotion video.

Renders an actual audx beat (built-in synth kit) to WAV and emits a JSON sidecar
describing it frame-by-frame at the video's fps, so the motion graphics can be
driven by the *real* audio: step-sequencer hits, per-track meter envelopes, and a
master waveform. The video's visuals therefore literally move to audx's own sound.

Run:  uv run python marketing/build-beat.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import soundfile as sf

from audx.arrangement import Arrangement, render_arrangement
from audx.pattern import Pattern
from audx.sampler import SampleLibrary

FPS = 30
BPM = 124.0
BARS = 12  # ~23s, comfortably covers a 20s (600-frame) video
SR = 44100
STEPS_PER_BAR = 16

# (name, dsl, hex colour) — these are the SAME patterns we render to audio,
# so the grid and the sound are guaranteed to agree.
TRACKS = [
    ("kick", "kick 4/4", "#ffb02e"),  # amber
    ("clap", "clap 2/8", "#ff2fb0"),  # magenta
    ("hats", "hh 16x8 | swing 10%", "#b6ff3d"),  # lime
    ("oh", "oh [0.0.1.0.0.0.1.0]", "#34f5ff"),  # cyan
    ("bass", "bass e(5,16) | tune -7st", "#5b8cff"),  # electric blue
    ("stab", "stab [1.0.0.0.0.0.1.0] | tune 3st", "#b86bff"),  # violet
    ("perc", "perc e(7,16,2)", "#ff6a3d"),  # hot orange
]

ROOT = Path(__file__).resolve().parent / "remotion"
WAV_OUT = ROOT / "public" / "audx-beat.wav"
JSON_OUT = ROOT / "src" / "beat-data.json"


def step_grid(pattern: Pattern) -> list[int]:
    """16-cell on/off grid for one bar from a parsed pattern."""
    grid = [0] * STEPS_PER_BAR
    for step in pattern.steps:
        idx = round(step.beat * 4) % STEPS_PER_BAR
        grid[idx] = 1
    return grid


def hit_frames(grid: list[int]) -> list[int]:
    """Absolute video-frame indices where this track fires, across all bars."""
    spb = 60.0 / BPM  # seconds per beat
    frames: list[int] = []
    for bar in range(BARS):
        for step, on in enumerate(grid):
            if not on:
                continue
            t = (bar * 4 + step / 4.0) * spb
            frames.append(round(t * FPS))
    return frames


def main() -> None:
    spb = 60.0 / BPM
    total_seconds = BARS * 4 * spb
    total_frames = int(np.ceil(total_seconds * FPS))

    arrangement = Arrangement(bpm=BPM)
    tracks_meta = []
    for name, dsl, color in TRACKS:
        pat = Pattern(name=name, dsl=dsl)
        pat.parse_dsl()
        arrangement.add(pat, start_bar=0, bars=BARS)
        grid = step_grid(pat)
        tracks_meta.append(
            {"name": name, "color": color, "steps": grid, "hits": hit_frames(grid)}
        )

    WAV_OUT.parent.mkdir(parents=True, exist_ok=True)
    library = SampleLibrary(Path("/nonexistent-empty"))  # synth-only
    render_arrangement(arrangement, library, WAV_OUT, sample_rate=SR)

    # Per-frame master envelope (RMS) from the rendered audio, normalised 0..1.
    audio, _ = sf.read(str(WAV_OUT), always_2d=True)
    mono = audio.mean(axis=1)
    samples_per_frame = SR / FPS
    env = np.zeros(total_frames, dtype=np.float64)
    for f in range(total_frames):
        a = int(f * samples_per_frame)
        b = int((f + 1) * samples_per_frame)
        chunk = mono[a:b]
        if chunk.size:
            env[f] = float(np.sqrt(np.mean(chunk**2)))
    if env.max() > 0:
        env = env / env.max()

    # Downsampled waveform peaks for a static scope drawing.
    n_peaks = 1400
    peaks = []
    win = max(1, len(mono) // n_peaks)
    for i in range(n_peaks):
        seg = mono[i * win : (i + 1) * win]
        peaks.append(round(float(np.max(np.abs(seg))) if seg.size else 0.0, 4))

    data = {
        "bpm": BPM,
        "fps": FPS,
        "bars": BARS,
        "stepsPerBar": STEPS_PER_BAR,
        "framesPerBar": (4 * spb) * FPS,
        "framesPerStep": (spb / 4) * FPS,
        "audioDurationFrames": total_frames,
        "tracks": tracks_meta,
        "envelope": [round(float(x), 4) for x in env],
        "waveform": peaks,
    }
    JSON_OUT.write_text(json.dumps(data))
    print(f"wrote {WAV_OUT} ({total_seconds:.1f}s) and {JSON_OUT}")
    print(f"  {len(tracks_meta)} tracks, {total_frames} frames @ {FPS}fps")


if __name__ == "__main__":
    main()

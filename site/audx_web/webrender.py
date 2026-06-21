"""Browser render path for the audx Pyodide playground.

Reuses the REAL audx DSL parser (``pattern.py``) and synth kit (``synth.py``) so
the in-browser sound matches the CLI. Runs both:

* in tests / on a dev machine, where the ``audx`` package is importable, and
* in Pyodide, where ``pattern`` and ``synth`` are loaded as flat modules.

``render_mix`` returns a ``(frames, 2)`` float32 stereo buffer — the page hands it
straight to the Web Audio API.
"""

from __future__ import annotations

import numpy as np

try:  # real package (tests, dev, CLI)
    from audx.pattern import Pattern
    from audx.synth import is_synth_voice, synth_voice
except ModuleNotFoundError:  # Pyodide: flat modules on sys.path
    from pattern import Pattern  # type: ignore[no-redef]
    from synth import is_synth_voice, synth_voice  # type: ignore[no-redef]


def render_mix(
    lines: list[str], bpm: float = 124.0, bars: int = 2, sr: int = 48000
) -> np.ndarray:
    """Render DSL ``lines`` (one pattern each) to a stereo float32 buffer.

    Built-in synth voices only — no samples — so it runs anywhere. Unknown
    instruments are skipped rather than erroring.
    """
    bpm = max(20.0, float(bpm))
    bars = max(1, int(bars))
    spb = 60.0 / bpm
    total_frames = int(np.ceil(bars * 4 * spb * sr))
    mix = np.zeros((total_frames, 2), dtype=np.float32)
    cache: dict[str, np.ndarray] = {}

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        pattern = Pattern(name="web", dsl=line)
        pattern.parse_dsl()
        for step in pattern.steps:
            name = step.sample
            if not is_synth_voice(name):
                continue
            tune = float(getattr(step, "tune_semitones", 0.0))
            key = f"{name}:{tune}"
            mono = cache.get(key)
            if mono is None:
                mono = synth_voice(name, sr, tune_semitones=tune)
                cache[key] = mono
            for bar in range(bars):
                beat = bar * 4 + pattern.swung_beat(step.beat)
                start = round(beat * spb * sr)
                end = min(start + len(mono), total_frames)
                if start >= total_frames or end <= start:
                    continue
                seg = mono[: end - start] * (step.velocity * 0.7)
                mix[start:end, 0] += seg
                mix[start:end, 1] += seg

    peak = float(np.max(np.abs(mix))) if mix.size else 0.0
    if peak > 1.0:
        mix /= peak
    return mix

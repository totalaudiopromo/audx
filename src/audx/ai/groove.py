"""Groove extraction from reference audio."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False


@dataclass
class GrooveProfile:
    bpm: float
    swing: float
    velocity_curve: list[float]
    step_activation: list[bool]


def extract_groove(path: Path, steps: int = 16) -> GrooveProfile | None:
    if not HAS_LIBROSA:
        print("[AI] librosa not available, install `[ai]` extras")
        return None

    import soundfile as sf
    y, sr = sf.read(str(path))
    if y.ndim > 1:
        y = y.mean(axis=1)

    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)  # type: ignore[attr-defined]
    bpm = float(tempo)

    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=512)  # type: ignore[attr-defined]
    bar_duration = 60.0 / bpm * 4
    step_dur = bar_duration / steps

    step_activation = [False] * steps
    times = librosa.times_like(onset_env, sr=sr, hop_length=512)
    for t in times:
        if t >= bar_duration:
            break
        idx = int(t / step_dur)
        if 0 <= idx < steps:
            step_activation[idx] = True

    max_str = max(onset_env) + 1e-8
    velocity_curve = [0.0] * steps
    for t, strength in zip(times, onset_env, strict=False):
        if t >= bar_duration:
            break
        idx = int(t / step_dur)
        if 0 <= idx < steps and strength > velocity_curve[idx]:
            velocity_curve[idx] = float(strength / max_str)

    return GrooveProfile(bpm=bpm, swing=0.0, velocity_curve=velocity_curve, step_activation=step_activation)


def groove_to_dsl(profile: GrooveProfile, instrument: str = "hh") -> str:
    hits = []
    for hit, vel in zip(profile.step_activation, profile.velocity_curve, strict=False):
        if hit:
            hits.append(f"x{vel:.2f}".lstrip("0"))
        else:
            hits.append("-")
    body = " ".join(hits)
    return f'{instrument} "{body}" | bpm {profile.bpm:.0f}'

"""Automatic sample tagging based on spectral features."""
from __future__ import annotations

from importlib.util import find_spec
from pathlib import Path

import numpy as np

HAS_LIBROSA = find_spec("librosa") is not None


def tag_sample(path: Path) -> list[str]:
    if not HAS_LIBROSA:
        return ["unknown"]

    import soundfile as sf
    y, _sr = sf.read(str(path))
    if y.ndim > 1:
        y = y.mean(axis=1)

    tags: list[str] = []

    spec = np.abs(np.fft.rfft(y))
    low_energy = spec[: len(spec) // 10].mean()
    total = spec.mean() + 1e-8
    if low_energy / total > 1.5:
        tags.append("subby")

    env = np.abs(y)
    peak = env.max()
    if peak > 0.8:
        tags.append("punchy")
    else:
        tags.append("soft")

    if spec[-len(spec) // 3:].mean() > total * 1.2:
        tags.append("bright")

    return tags


def tag_directory(folder: Path) -> dict[str, list[str]]:
    tags: dict[str, list[str]] = {}
    for wav in folder.rglob("*.wav"):
        tags[wav.name] = tag_sample(wav)
    return tags

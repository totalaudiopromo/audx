"""Heartmula bridge.

This module is intentionally a subprocess bridge, not an in-process model host.
It checks whether Chris's local heartlib checkout exists and shells out to it.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

HEARTLIB_DIR = Path.home() / "workspace" / "active" / "heartlib"
HEARTLIB_VENV_PYTHON = HEARTLIB_DIR / ".venv" / "bin" / "python"
HEARTLIB_EXAMPLE = HEARTLIB_DIR / "examples" / "run_music_generation.py"


@dataclass(frozen=True)
class HeartmulaStatus:
    available: bool
    reason: str


def status() -> HeartmulaStatus:
    if not HEARTLIB_DIR.exists():
        return HeartmulaStatus(False, f"heartlib checkout missing: {HEARTLIB_DIR}")
    if not HEARTLIB_VENV_PYTHON.exists():
        return HeartmulaStatus(False, f"heartlib venv missing: {HEARTLIB_VENV_PYTHON}")
    if not HEARTLIB_EXAMPLE.exists():
        return HeartmulaStatus(False, f"generation script missing: {HEARTLIB_EXAMPLE}")
    return HeartmulaStatus(True, "heartlib bridge available")


def generate(prompt: str, output_path: Path, *, bpm: int = 128, bars: int = 4) -> Path:
    check = status()
    if not check.available:
        raise RuntimeError(check.reason)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(HEARTLIB_VENV_PYTHON),
        str(HEARTLIB_EXAMPLE),
        "--model_path",
        str(HEARTLIB_DIR / "ckpt"),
        "--version",
        "3B",
        "--lyrics",
        prompt,
        "--tags",
        f"audx bpm {bpm}",
        "--save_path",
        str(output_path),
        "--max_audio_length_ms",
        str(max(1, bars) * 120_000),
        "--lazy_load",
        "true",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=HEARTLIB_DIR, timeout=60 * 30)
    if result.returncode != 0:
        raise RuntimeError(f"Heartmula failed: {result.stderr[-1000:]}")
    return output_path

"""Latency calibration (spec §11 `audx rec --calibrate`).

Plays an impulse, captures it via the input device, and stores the measured
round-trip latency in ``CONFIG_DIR/calibration.json`` so future ``audx rec``
invocations can offset the input buffer accordingly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from audx.config import CONFIG_DIR

CALIBRATION_PATH = CONFIG_DIR / "calibration.json"


@dataclass
class Calibration:
    latency_ms: float
    measured_at: str
    notes: str = ""


def load() -> Calibration | None:
    if not CALIBRATION_PATH.exists():
        return None
    try:
        data = json.loads(CALIBRATION_PATH.read_text())
    except json.JSONDecodeError:
        return None
    return Calibration(
        latency_ms=float(data.get("latency_ms", 0.0)),
        measured_at=str(data.get("measured_at", "")),
        notes=str(data.get("notes", "")),
    )


def save(latency_ms: float, notes: str = "") -> Path:
    from datetime import datetime

    payload = {
        "latency_ms": float(latency_ms),
        "measured_at": datetime.now().isoformat(),
        "notes": notes,
    }
    CALIBRATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    CALIBRATION_PATH.write_text(json.dumps(payload, indent=2))
    return CALIBRATION_PATH


def measure_impulse(duration_s: float = 1.0, sample_rate: int = 44100) -> float:
    """Play an impulse and measure its arrival in the input stream.

    Returns measured latency in ms. Requires both an output and input device.
    Falls back to a sensible default if no input is available.
    """
    try:
        import numpy as np
        import sounddevice as sd  # type: ignore[import-not-found]
    except Exception:
        return 0.0

    import numpy as np

    impulse = np.zeros(int(duration_s * sample_rate), dtype="float32")
    impulse[0] = 1.0
    try:
        recording = sd.playrec(impulse, samplerate=sample_rate, channels=1, dtype="float32")
        sd.wait()
    except Exception:
        return 0.0
    if recording is None:
        return 0.0
    flat = np.abs(np.asarray(recording).flatten())
    peak_frame = int(np.argmax(flat)) if flat.size else 0
    return (peak_frame / sample_rate) * 1000.0

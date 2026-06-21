"""Generate golden-vector fixtures for the TypeScript DSL parser port.

Runs the REAL ``audx.pattern`` parser over a spread of DSL inputs and writes the
parsed result to ``web/fixtures/*.json``. The TS port (web/src/dsl.ts) is tested
against these, so the browser parser provably matches the Python one — including
the awkward bits (``16x8`` = 16 hits, banker's rounding in swing, sample-name
aliases, modifier clamping).

Run: ``python scripts/gen_web_fixtures.py`` (CI/tests assert the output is current).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from audx.pattern import Pattern
from audx.synth import SYNTH_VOICES, synth_voice

SR = 48000
# Voices the TS port matches sample-for-sample. Excludes the noise voices (numpy's
# PCG64 isn't reproducible in JS) and cowbell, whose np.sign() flips at zero
# crossings on ~1e-16 float differences — deterministic but not bitwise-portable.
EXACT = {
    "sub", "rim", "tom", "perc",
    "bass", "pluck", "stab", "keys", "saw", "sine",
}
DECIMATE_TARGET = 512
ENV_WINDOWS = 64

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "web" / "fixtures"

# One DSL string per case, chosen to exercise every grammar branch + modifier.
DSL_CASES: list[str] = [
    "kick 4/4",
    "snare 2/8",
    "hh 16x8",
    "hh 8x8",
    "perc 1/4",
    "kick 3/4",
    "perc e(5,16)",
    "perc e(5,16,2)",
    "bass e(7,16)",
    "clap [1.0.1.0.1.1.0.0]",
    "[1.0.1.0]",
    "kick [1 0 1 0 1 0 1 0]",
    "x---x-----x---x-",
    "x-x---x-x-x---x-",
    "bd 4/4 | vel 0.5 | ch 2",
    "hh 16x8 | swing 12%",
    "bass e(5,16) | tune -7st",
    "stab [1.0.0.0] | tune 3st | pan L50",
    "keys 4/4 | gain -3db | pan R100",
    "kick 4/4 | humanize 8% | chance 70%",
    "oh 2/8 | pan C",
    "hat 4/4",
    "sd 4/4",
    "rim 16x8 | vel 0.6",
    "kick 4/4 | vel 0",
]


def _step_dict(step: object) -> dict:
    s = step  # type: ignore[assignment]
    return {
        "sample": s.sample,
        "beat": s.beat,
        "velocity": s.velocity,
        "channel": s.channel,
        "gain_db": s.gain_db,
        "pan": s.pan,
        "tune_semitones": s.tune_semitones,
    }


def build_dsl_fixtures() -> list[dict]:
    cases = []
    for dsl in DSL_CASES:
        pat = Pattern(name="t", dsl=dsl)
        pat.parse_dsl()
        cases.append(
            {
                "dsl": dsl,
                "length_beats": pat.length_beats,
                "swing": pat.swing,
                "humanize": pat.humanize,
                "chance": pat.chance,
                "gain_db": pat.gain_db,
                "pan": pat.pan,
                "tune_semitones": pat.tune_semitones,
                "steps": [_step_dict(s) for s in pat.steps],
            }
        )
    return cases


def build_swing_fixtures() -> list[dict]:
    """swung_beat() parity — catches Python's round-half-to-even."""
    beats = [i * 0.25 for i in range(16)]
    cases = []
    for swing in (0.0, 0.1, 0.25, 0.5, 0.66):
        pat = Pattern(name="s", dsl="hh 16x8")
        pat.swing = swing
        cases.append(
            {
                "swing": swing,
                "length_beats": pat.length_beats,
                "beats": beats,
                "expect": [pat.swung_beat(b) for b in beats],
            }
        )
    return cases


def _windowed_rms(buf: np.ndarray) -> list[float]:
    n = len(buf)
    out = []
    for i in range(ENV_WINDOWS):
        seg = buf[(i * n) // ENV_WINDOWS : ((i + 1) * n) // ENV_WINDOWS]
        out.append(math.sqrt(float(np.mean(seg**2))) if seg.size else 0.0)
    return out


def _voice_ref(name: str, *, tune: float = 0.0) -> dict:
    buf = synth_voice(name, SR, tune_semitones=tune, seed=0).astype(np.float64)
    n = len(buf)
    stride = max(1, n // DECIMATE_TARGET)
    return {
        "voice": name,
        "tune": tune,
        "exact": name in EXACT,
        "n": n,
        "stride": stride,
        "peak": float(np.max(np.abs(buf))) if n else 0.0,
        "rms": math.sqrt(float(np.mean(buf**2))) if n else 0.0,
        "decimated": [float(buf[i]) for i in range(0, n, stride)],
        "env": _windowed_rms(buf),
    }


def build_synth_fixtures() -> list[dict]:
    refs = [_voice_ref(v) for v in SYNTH_VOICES]
    # a couple of repitched references to exercise the resampler
    refs.append(_voice_ref("sine", tune=-7.0))
    refs.append(_voice_ref("bass", tune=5.0))
    return refs


def main() -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    (FIXTURE_DIR / "dsl.json").write_text(
        json.dumps(build_dsl_fixtures(), indent=2) + "\n"
    )
    (FIXTURE_DIR / "swing.json").write_text(
        json.dumps(build_swing_fixtures(), indent=2) + "\n"
    )
    (FIXTURE_DIR / "synth.json").write_text(
        json.dumps(build_synth_fixtures()) + "\n"
    )
    print(f"wrote fixtures to {FIXTURE_DIR}")


if __name__ == "__main__":
    main()

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
from pathlib import Path

from audx.pattern import Pattern

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


def main() -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    (FIXTURE_DIR / "dsl.json").write_text(
        json.dumps(build_dsl_fixtures(), indent=2) + "\n"
    )
    (FIXTURE_DIR / "swing.json").write_text(
        json.dumps(build_swing_fixtures(), indent=2) + "\n"
    )
    print(f"wrote fixtures to {FIXTURE_DIR}")


if __name__ == "__main__":
    main()

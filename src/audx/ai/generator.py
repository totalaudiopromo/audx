"""Pattern generation from text descriptions."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal

from audx.pattern import Pattern, Step

DEFAULT_VELOCITY_RANGES = {
    "low": (0.2, 0.4),
    "med": (0.45, 0.7),
    "high": (0.75, 1.0),
}

DEFAULT_SWING = {
    "straight": 0.0,
    "loose": 0.55,
    "tight": 0.35,
}


@dataclass
class GenerationParams:
    instrument: str = "kick"
    subdivision: str = "16"
    density: float = 0.5
    swing: str = "straight"
    velocity_profile: str = "med"
    stutter_prob: float = 0.0
    channel: int = 0


@dataclass
class GenResult:
    pattern: Pattern
    params: GenerationParams
    engine: Literal["heuristic", "heartlib"]


# ── helpers ────────────────────────────────────────────────────────────────────

def pattern_to_grid(pattern: Pattern, steps: int = 16) -> str:
    step_width = 4.0 / steps
    grid = ["-"] * steps
    for step in pattern.steps:
        idx = round(step.beat / step_width)
        if 0 <= idx < steps:
            grid[idx] = "x"
    groups = ["".join(grid[i:i+4]) for i in range(0, steps, 4)]
    return " ".join(groups)


def parse_description(desc: str) -> GenerationParams:
    d = desc.lower()
    p = GenerationParams()

    if any(w in d for w in ["kick", "bass drum", "sub"]):
        p.instrument = "kick"
        p.density = 0.3 if "sparse" in d else 0.6
    elif any(w in d for w in ["snare", "clap", "rim"]):
        p.instrument = "snare"
        p.density = 0.4
    elif any(w in d for w in ["hihat", "hat", "hh", "closed", "open"]):
        p.instrument = "hh"
        p.density = 0.7
        if "open" in d:
            p.instrument = "oh"
    elif any(w in d for w in ["perc", "conga", "bongo"]):
        p.instrument = "perc"
        p.density = 0.5

    if "8th" in d or "8note" in d:
        p.subdivision = "8"
    elif "32" in d:
        p.subdivision = "32"

    for key in DEFAULT_SWING:
        if key in d:
            p.swing = key
            break

    for key in ["low", "med", "high"]:
        if key in d:
            p.velocity_profile = key
            break

    if "stutter" in d or "roll" in d:
        p.stutter_prob = 0.2

    return p


def build_heuristic_pattern(params: GenerationParams) -> Pattern:
    sub_map = {"8": 8, "16": 16, "32": 32}
    n = sub_map[params.subdivision]
    vel_range = DEFAULT_VELOCITY_RANGES[params.velocity_profile]
    swing_offset = DEFAULT_SWING[params.swing]
    step_width = 4.0 / n
    steps: list[Step] = []

    i = 0
    while i < n:
        hit = random.random() < params.density
        if hit and params.stutter_prob > 0 and random.random() < params.stutter_prob and i < n - 1:
            v1 = random.uniform(*vel_range)
            v1 = max(0.1, min(1.0, v1 + random.uniform(-0.05, 0.05)))
            v2 = max(0.1, v1 * 0.8)
            steps.append(Step(sample=params.instrument, velocity=v1, channel=params.channel, beat=i * step_width))
            steps.append(Step(sample=params.instrument, velocity=v2, channel=params.channel, beat=(i+1)*step_width))
            i += 2
            continue
        if hit:
            v = random.uniform(*vel_range)
            v = max(0.1, min(1.0, v + random.uniform(-0.05, 0.05)))
            steps.append(Step(sample=params.instrument, velocity=v, channel=params.channel, beat=i * step_width))
        i += 1

    return Pattern(name="generated", dsl="<heuristic>", steps=steps, swing=swing_offset, channel=params.channel)


def _heartlib_available() -> bool:
    try:
        import heartlib.pipelines.music_generation  # noqa: F401
        return True
    except ImportError:
        return False


def generate(desc: str, channel: int = 0) -> GenResult:
    params = parse_description(desc)
    params.channel = channel
    print(f"[AI] parsed: instrument={params.instrument}, subdivision={params.subdivision}, swing={params.swing}")

    if _heartlib_available():
        print("[AI] heartlib detected (would use model), heuristic for now")

    pattern = build_heuristic_pattern(params)
    return GenResult(pattern=pattern, params=params, engine="heuristic")

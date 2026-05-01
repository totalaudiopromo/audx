"""Pattern DSL and deterministic step scheduler."""

from __future__ import annotations

import random
import re
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class Step:
    """A single scheduled sample trigger."""

    sample: str
    velocity: float = 1.0
    duration: float = 1.0
    channel: int = 0
    beat: float = 0.0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.velocity = max(0.0, min(float(self.velocity), 1.0))
        self.channel = max(0, int(self.channel))
        self.beat = float(self.beat)


@dataclass
class Pattern:
    """A repeating bar-length pattern.

    Supported DSL:
    - ``kick 4/4``: four hits across four beats
    - ``hh 16x8``: sixteen hits across four beats (legacy suffix ignored)
    - ``x--- -x-- --x- ---x``: x/rest grid, default sample inferred from name
    - pipe modifiers: ``kick 4/4 | vel 0.7 | channel 2 | swing 0.55``
    """

    name: str
    dsl: str
    length_beats: float = 4.0
    channel: int = 0
    steps: list[Step] = field(default_factory=list)
    swing: float = 0.0
    humanize: float = 0.0
    metadata: dict = field(default_factory=dict)

    def parse_dsl(self) -> None:
        dsl = self.dsl.strip()
        if not dsl:
            self.steps = []
            return

        base, opts = self._split_options(dsl)
        self.swing = self._parse_swing(opts.get("swing", self.swing))
        velocity = float(opts.get("vel", opts.get("velocity", 0.8)) or 0.8)
        channel = int(opts.get("ch", opts.get("channel", self.channel)) or 0)

        if re.fullmatch(r"[\sxX.\-]+", base):
            self._parse_grid(base, velocity=velocity, channel=channel)
        else:
            self._parse_instrument(base, velocity=velocity, channel=channel)

    @staticmethod
    def _parse_swing(value: object) -> float:
        if value is None:
            parsed = 0.0
        elif isinstance(value, str) and value.endswith("%"):
            parsed = float(value[:-1]) / 100.0
        elif isinstance(value, (str, int, float)):
            parsed = float(value)
        else:
            parsed = 0.0
        return max(0.0, min(parsed, 1.0))

    @staticmethod
    def _split_options(dsl: str) -> tuple[str, dict[str, str]]:
        parts = [part.strip() for part in dsl.split("|")]
        opts: dict[str, str] = {}
        for opt in parts[1:]:
            if not opt:
                continue
            bits = opt.split(None, 1)
            opts[bits[0].lower()] = bits[1] if len(bits) > 1 else "true"
        return parts[0], opts

    def _parse_grid(self, grid: str, velocity: float, channel: int) -> None:
        cleaned = grid.replace(" ", "")
        if not cleaned:
            self.steps = []
            return
        step_width = self.length_beats / len(cleaned)
        sample = self._sample_name_from_instr(self.name)
        self.steps = [
            Step(sample=sample, velocity=velocity, channel=channel, beat=i * step_width)
            for i, char in enumerate(cleaned)
            if char.lower() == "x"
        ]

    def _parse_instrument(self, base: str, velocity: float, channel: int) -> None:
        parts = base.split(None, 1)
        instr = parts[0]
        sample = self._sample_name_from_instr(instr)
        spec = parts[1].strip() if len(parts) > 1 else "1/4"

        hits = 1
        if "/" in spec:
            hits = int(spec.split("/", 1)[0])
        elif "x" in spec.lower():
            hits = int(spec.lower().split("x", 1)[0])

        hits = max(1, hits)
        step_width = self.length_beats / hits
        self.steps = [
            Step(sample=sample, velocity=velocity, channel=channel, beat=i * step_width)
            for i in range(hits)
        ]

    @staticmethod
    def _sample_name_from_instr(instr: str) -> str:
        mapping = {
            "bd": "kick",
            "kick": "kick",
            "sd": "snare",
            "snare": "snare",
            "hh": "hihat",
            "hat": "hihat",
            "hihat": "hihat",
            "oh": "openhat",
            "clap": "clap",
            "rim": "rim",
            "perc": "percussion",
        }
        return mapping.get(instr.lower(), instr)

    def events_due(self, previous_beat: float, current_beat: float) -> list[Step]:
        """Return steps crossed between previous_beat and current_beat.

        Swing is applied as a real timing offset by delaying off-grid 8th/16th
        steps. ``swing=0.5`` pushes every odd 16th later by half a 16th.
        """
        events: list[Step] = []
        for step in self.steps:
            beat = self.swung_beat(step.beat)
            if _beat_crossed(previous_beat, current_beat, beat, self.length_beats):
                events.append(step)
        return events

    def swung_beat(self, beat: float) -> float:
        if self.swing <= 0:
            return beat % self.length_beats
        sixteenth = self.length_beats / 16.0
        index = round(beat / sixteenth)
        if index % 2 == 1:
            beat += sixteenth * self.swing
        return beat % self.length_beats


def _beat_crossed(previous: float, current: float, target: float, length: float) -> bool:
    previous %= length
    current %= length
    target %= length
    if previous == current:
        return target == current
    if previous < current:
        return previous < target <= current
    return target > previous or target <= current


class PatternEngine:
    """Callback-safe scheduler with accumulated time and real swing offsets."""

    def __init__(self, bpm: float = 120.0, resolution: int = 16):
        self.bpm = bpm
        self.resolution = resolution
        self.patterns: dict[str, Pattern] = {}
        self.current_bar = 0
        self.current_beat = 0.0
        self.running = False
        self.callbacks: list[Callable] = []
        self._absolute_beat = 0.0
        self._last_absolute_beat = 0.0
        self._emit_downbeat = False

    def add_pattern(self, pattern: Pattern) -> None:
        if not pattern.steps:
            pattern.parse_dsl()
        self.patterns[pattern.name] = pattern

    def remove_pattern(self, name: str) -> bool:
        return self.patterns.pop(name, None) is not None

    def set_bpm(self, bpm: float) -> None:
        self.bpm = max(1.0, float(bpm))

    def start(self) -> None:
        self.running = True
        self.current_bar = 0
        self.current_beat = 0.0
        self._absolute_beat = 0.0
        self._last_absolute_beat = 0.0
        self._emit_downbeat = True

    def stop(self) -> None:
        self.running = False

    def tick(self, delta_time: float) -> list[Step]:
        if not self.running:
            return []

        fired: list[Step] = []
        if self._emit_downbeat:
            fired.extend(self._events_between(0.0, 0.0))
            self._emit_downbeat = False

        beats_elapsed = max(0.0, float(delta_time)) / (60.0 / self.bpm)
        if beats_elapsed <= 0:
            return fired

        previous = self._absolute_beat
        current = self._absolute_beat + beats_elapsed
        fired.extend(self._events_between(previous, current))
        self._last_absolute_beat = previous
        self._absolute_beat = current
        self.current_bar = int(self._absolute_beat // 4.0)
        self.current_beat = self._absolute_beat % 4.0
        return fired

    def _events_between(self, previous_absolute: float, current_absolute: float) -> list[Step]:
        events: list[Step] = []
        for pattern in self.patterns.values():
            if pattern.metadata.get("enabled", True):
                previous = previous_absolute % pattern.length_beats
                current = current_absolute % pattern.length_beats
                events.extend(pattern.events_due(previous, current))
        for callback in self.callbacks:
            callback(self.current_beat, events)
        return events

    def on_tick(self, callback: Callable) -> None:
        self.callbacks.append(callback)


def four_on_floor() -> list[Pattern]:
    return [Pattern(name="kick", dsl="kick 4/4 | channel 0")]


def breakbeat() -> list[Pattern]:
    return [
        Pattern(name="kick", dsl="x---x-----x---x- | channel 0"),
        Pattern(name="snare", dsl="----x-------x--- | channel 1"),
        Pattern(name="hihat", dsl="hh 16x8 | channel 2 | vel 0.55"),
    ]


def hihat_variations() -> list[Pattern]:
    return [
        Pattern(name="hh_8", dsl="hh 8x8 | channel 2 | vel 0.55"),
        Pattern(name="hh_16", dsl="hh 16x8 | channel 2 | vel 0.45"),
        Pattern(name="hh_sparse", dsl="x-x---x-x-x---x- | channel 2 | vel 0.6"),
    ]


class MarkovChain:
    """Tiny Markov helper for off-line pattern generation."""

    def __init__(self, states: list[str], transitions: dict[str, dict[str, float]] | None = None):
        if not states:
            raise ValueError("MarkovChain requires at least one state")
        self.states = states
        self.transitions = transitions or {
            state: {target: 1.0 / len(states) for target in states} for state in states
        }
        self.current: str | None = None

    @classmethod
    def from_sequence(cls, sequence: list[str]) -> MarkovChain:
        if not sequence:
            raise ValueError("sequence cannot be empty")
        states = list(dict.fromkeys(sequence))
        counts: dict[str, dict[str, int]] = {state: {} for state in states}
        for current, nxt in zip(sequence, sequence[1:], strict=False):
            counts.setdefault(current, {})[nxt] = counts.setdefault(current, {}).get(nxt, 0) + 1
        transitions: dict[str, dict[str, float]] = {}
        for state in states:
            total = sum(counts.get(state, {}).values())
            if total == 0:
                transitions[state] = {target: 1.0 / len(states) for target in states}
            else:
                transitions[state] = {target: count / total for target, count in counts[state].items()}
        return cls(states, transitions)

    def step(self) -> str:
        if self.current is None:
            self.current = random.choice(self.states)
            return self.current
        distribution = self.transitions.get(self.current, {})
        roll = random.random()
        cumulative = 0.0
        for state, probability in distribution.items():
            cumulative += probability
            if roll <= cumulative:
                self.current = state
                return state
        self.current = random.choice(self.states)
        return self.current

    def generate_pattern(self, length: int = 16, name: str = "markov") -> Pattern:
        grid = []
        for _ in range(length):
            grid.append("-" if self.step() in {"-", "rest", "silence"} else "x")
        pattern = Pattern(name=name, dsl="".join(grid))
        pattern.parse_dsl()
        return pattern


def euclidean_rhythm(pulses: int, steps: int, sample: str = "kick", name: str | None = None) -> Pattern:
    if pulses < 0 or steps <= 0 or pulses > steps:
        raise ValueError("euclidean_rhythm requires 0 <= pulses <= steps")
    grid = ["-" for _ in range(steps)]
    bucket = 0
    for i in range(steps):
        bucket += pulses
        if bucket >= steps:
            bucket -= steps
            grid[i] = "x"
    pattern = Pattern(name=name or f"{sample}_e{pulses}_{steps}", dsl="".join(grid))
    pattern.parse_dsl()
    for step in pattern.steps:
        step.sample = sample
    return pattern


_engine: PatternEngine | None = None


def get_pattern_engine() -> PatternEngine:
    global _engine
    if _engine is None:
        _engine = PatternEngine()
    return _engine

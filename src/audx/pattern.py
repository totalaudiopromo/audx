"""Pattern DSL and deterministic step scheduler."""

from __future__ import annotations

import random
import re
import shlex
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Step:
    """A single scheduled sample trigger."""

    sample: str
    velocity: float = 1.0
    duration: float = 1.0
    channel: int = 0
    beat: float = 0.0
    gain_db: float = 0.0
    pan: float = 0.0
    tune_semitones: float = 0.0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.velocity = max(0.0, min(float(self.velocity), 1.0))
        self.channel = max(0, int(self.channel))
        self.beat = float(self.beat)
        self.pan = max(-1.0, min(float(self.pan), 1.0))


@dataclass
class Pattern:
    """A repeating bar-length pattern.

    Supported DSL (spec §05):
    - ``kick 4/4``                            four on the floor
    - ``hh 16x8``                             eight evenly-spaced hits over 16 steps
    - ``snare 2/8``                           hits on beats 2 and 4
    - ``perc e(5,16)`` / ``perc e(5,16,2)``   Euclidean rhythm, optional rotation
    - ``clap [1.0.1.0.1.1.0.0]``              explicit grid (1 = hit, 0/. = rest)
    - ``x--- -x-- --x- ---x``                 legacy x/rest grid

    Pipe modifiers (``base | op arg | op arg ...``):
    - ``vel``/``velocity``                    0.0-1.0
    - ``ch``/``channel``                      mixer channel index
    - ``swing``                               percent or 0..1
    - ``humanize``                            timing/velocity jitter, percent or 0..1
    - ``chance``                              per-step trigger probability
    - ``gain``                                ±dB
    - ``pan``                                 L100..R100 or -1..1
    - ``tune``                                ±semitones
    """

    name: str
    dsl: str
    length_beats: float = 4.0
    channel: int = 0
    steps: list[Step] = field(default_factory=list)
    swing: float = 0.0
    humanize: float = 0.0
    chance: float = 1.0
    gain_db: float = 0.0
    pan: float = 0.0
    tune_semitones: float = 0.0
    metadata: dict = field(default_factory=dict)

    def parse_dsl(self) -> None:
        dsl = self.dsl.strip()
        if not dsl:
            self.steps = []
            return

        base, opts = self._split_options(dsl)
        self.swing = self._parse_swing(opts.get("swing", self.swing))
        self.humanize = self._parse_percent(opts.get("humanize", self.humanize))
        self.chance = self._parse_chance(opts.get("chance", self.chance))
        self.gain_db = _parse_db(opts.get("gain", self.gain_db))
        self.pan = _parse_pan(opts.get("pan", self.pan))
        self.tune_semitones = _parse_semitones(opts.get("tune", self.tune_semitones))
        velocity = float(opts.get("vel", opts.get("velocity", 0.8)) or 0.8)
        channel = int(opts.get("ch", opts.get("channel", self.channel)) or 0)
        self.channel = channel

        grid_match = re.search(r"\[([^\[\]]+)\]", base)
        if base.startswith("[") and base.endswith("]"):
            self._parse_explicit_grid(base[1:-1], velocity=velocity, channel=channel)
        elif grid_match:
            prefix = base[: grid_match.start()].strip()
            if prefix:
                instr = prefix.split(None, 1)[0]
                self.name = self.name or instr
                self._parse_explicit_grid(
                    grid_match.group(1),
                    velocity=velocity,
                    channel=channel,
                    sample_hint=instr,
                )
            else:
                self._parse_explicit_grid(grid_match.group(1), velocity=velocity, channel=channel)
        elif _EUCLID_RE.search(base):
            self._parse_euclid(base, velocity=velocity, channel=channel)
        elif re.fullmatch(r"[\sxX.\-]+", base):
            self._parse_grid(base, velocity=velocity, channel=channel)
        else:
            self._parse_instrument(base, velocity=velocity, channel=channel)

        for step in self.steps:
            step.gain_db = self.gain_db
            step.pan = self.pan
            step.tune_semitones = self.tune_semitones

    @staticmethod
    def _parse_swing(value: object) -> float:
        return _parse_percent(value, default=0.0)

    @staticmethod
    def _parse_percent(value: object) -> float:
        return _parse_percent(value, default=0.0)

    @staticmethod
    def _parse_chance(value: object) -> float:
        return _parse_percent(value, default=1.0)

    @staticmethod
    def _split_options(dsl: str) -> tuple[str, dict[str, str]]:
        parts = [part.strip() for part in _smart_split(dsl, "|")]
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
        parts = shlex.split(base)
        if not parts:
            self.steps = []
            return

        instr = parts[0]
        sample = self._sample_name_from_instr(instr)
        spec = "1/4"

        if len(parts) >= 3 and _looks_like_sample_path(parts[1]):
            sample = parts[1]
            spec = " ".join(parts[2:])
        elif len(parts) >= 2 and _looks_like_sample_path(parts[0]):
            sample = parts[0]
            instr = Path(parts[0]).stem
            self.name = self.name or instr
            spec = " ".join(parts[1:])
        elif len(parts) > 1:
            spec = " ".join(parts[1:])

        beats = self._beats_for_spec(spec)
        self.steps = [
            Step(sample=sample, velocity=velocity, channel=channel, beat=beat)
            for beat in beats
        ]

    def _beats_for_spec(self, spec: str) -> list[float]:
        spec = spec.strip()
        # 16x8 → 8 hits across 16 steps
        if "x" in spec.lower() and "/" not in spec:
            hits_str, _, _ = spec.lower().partition("x")
            hits = max(1, int(hits_str or "1"))
            step_width = self.length_beats / hits
            return [i * step_width for i in range(hits)]
        # 4/4 (every beat) and 2/8 (beats 2 and 4)
        if "/" in spec:
            n_str, _, m_str = spec.partition("/")
            n = max(1, int(n_str or "1"))
            m = max(1, int(m_str or "4"))
            if n == m or m == 4:
                # 4/4 → hit on every beat
                step_width = self.length_beats / n
                return [i * step_width for i in range(n)]
            if m == 8:
                # 2/8 → hits on beats 2 and 4 of a 4-beat bar
                if n == 2:
                    return [1.0 * (self.length_beats / 4.0), 3.0 * (self.length_beats / 4.0)]
                # generic: distribute n hits over m eighth-notes starting at 2nd
                step_width = self.length_beats / m
                return [(2 * i + 1) * step_width for i in range(n)]
            step_width = self.length_beats / n
            return [i * step_width for i in range(n)]
        return [0.0]

    def _parse_euclid(self, base: str, velocity: float, channel: int) -> None:
        match = _EUCLID_RE.search(base)
        if not match:
            self.steps = []
            return
        pulses = max(0, int(match.group(1)))
        steps = max(1, int(match.group(2)))
        rotation = int(match.group(3)) if match.group(3) else 0
        prefix = base[: match.start()].strip()
        instr = prefix.split(None, 1)[0] if prefix else self.name
        sample = self._sample_name_from_instr(instr)
        grid = _euclidean_grid(pulses, steps, rotation)
        step_width = self.length_beats / steps
        self.steps = [
            Step(sample=sample, velocity=velocity, channel=channel, beat=i * step_width)
            for i, hit in enumerate(grid)
            if hit
        ]

    def _parse_explicit_grid(
        self,
        inner: str,
        velocity: float,
        channel: int,
        sample_hint: str | None = None,
    ) -> None:
        cells = [c for c in re.split(r"[\s,]+", inner) if c]
        if len(cells) == 1 and len(cells[0]) > 1:
            cells = list(cells[0])
        if not cells:
            self.steps = []
            return
        step_width = self.length_beats / len(cells)
        sample = self._sample_name_from_instr(sample_hint or self.name)
        self.steps = [
            Step(sample=sample, velocity=velocity, channel=channel, beat=i * step_width)
            for i, cell in enumerate(cells)
            if cell.strip().lower() in {"1", "x", "*"}
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

        Chance and humanize are applied at fire time so each pass through the
        bar produces a fresh variation. Chance probabilistically drops the
        step; humanize jitters velocity by ±humanize.
        """
        events: list[Step] = []
        for step in self.steps:
            beat = self.swung_beat(step.beat)
            if not _beat_crossed(previous_beat, current_beat, beat, self.length_beats):
                continue
            if self.chance < 1.0 and random.random() > self.chance:
                continue
            if self.humanize > 0:
                jitter = (random.random() - 0.5) * 2 * self.humanize
                fired = Step(
                    sample=step.sample,
                    velocity=max(0.0, min(1.0, step.velocity * (1 + jitter * 0.5))),
                    duration=step.duration,
                    channel=step.channel,
                    beat=step.beat,
                    gain_db=step.gain_db,
                    pan=step.pan,
                    tune_semitones=step.tune_semitones,
                    metadata=dict(step.metadata),
                )
                events.append(fired)
            else:
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


_EUCLID_RE = re.compile(r"e\(\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*(-?\d+))?\s*\)", re.IGNORECASE)


def _smart_split(text: str, sep: str) -> list[str]:
    """Split on ``sep`` but ignore separators inside [], (), or quotes."""
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    quote: str | None = None
    for ch in text:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in ('"', "'"):
            quote = ch
            buf.append(ch)
        elif ch in "([":
            depth += 1
            buf.append(ch)
        elif ch in ")]":
            depth = max(0, depth - 1)
            buf.append(ch)
        elif ch == sep and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    return parts


def _parse_percent(value: object, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("%"):
            try:
                return max(0.0, min(float(text[:-1]) / 100.0, 1.0))
            except ValueError:
                return default
        try:
            num = float(text)
        except ValueError:
            return default
    else:
        try:
            num = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return default
    return max(0.0, min(num, 1.0))


def _parse_db(value: object) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().lower().rstrip("db")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _parse_pan(value: object) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return max(-1.0, min(float(value), 1.0))
    text = str(value).strip().upper()
    if text in {"C", "CENTRE", "CENTER"}:
        return 0.0
    if text.startswith("L"):
        try:
            return max(-1.0, -float(text[1:]) / 100.0)
        except ValueError:
            return 0.0
    if text.startswith("R"):
        try:
            return min(1.0, float(text[1:]) / 100.0)
        except ValueError:
            return 0.0
    try:
        return max(-1.0, min(float(text), 1.0))
    except ValueError:
        return 0.0


def _parse_semitones(value: object) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().lower().rstrip("st").rstrip("s")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _looks_like_sample_path(value: str) -> bool:
    suffix = Path(value).suffix.lower()
    return "/" in value or "\\" in value or suffix in {".wav", ".flac", ".mp3", ".ogg", ".aiff", ".aif"}


def _euclidean_grid(pulses: int, steps: int, rotation: int = 0) -> list[int]:
    if pulses < 0 or steps <= 0:
        return [0] * max(steps, 0)
    pulses = min(pulses, steps)
    grid = [0] * steps
    bucket = 0
    for i in range(steps):
        bucket += pulses
        if bucket >= steps:
            bucket -= steps
            grid[i] = 1
    if rotation:
        rotation = rotation % steps
        grid = grid[-rotation:] + grid[:-rotation]
    return grid


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


def euclidean_rhythm(
    pulses: int,
    steps: int,
    sample: str = "kick",
    name: str | None = None,
    rotation: int = 0,
) -> Pattern:
    if pulses < 0 or steps <= 0 or pulses > steps:
        raise ValueError("euclidean_rhythm requires 0 <= pulses <= steps")
    grid = ["x" if cell else "-" for cell in _euclidean_grid(pulses, steps, rotation)]
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

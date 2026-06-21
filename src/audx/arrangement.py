"""Arrangement model and offline rendering helpers."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from audx.pattern import Pattern
from audx.sampler import SampleLibrary
from audx.synth import is_synth_voice, synth_voice


@dataclass
class Clip:
    """A pattern placed on a timeline."""

    pattern: Pattern
    start_bar: int = 0
    bars: int = 1


@dataclass
class Arrangement:
    """Simple bar-based arrangement."""

    bpm: float = 128.0
    clips: list[Clip] = field(default_factory=list)

    def add(self, pattern: Pattern, start_bar: int = 0, bars: int = 1) -> None:
        if not pattern.steps:
            pattern.parse_dsl()
        self.clips.append(Clip(pattern=pattern, start_bar=start_bar, bars=max(1, bars)))

    @property
    def total_bars(self) -> int:
        if not self.clips:
            return 0
        return max(clip.start_bar + clip.bars for clip in self.clips)


@dataclass
class Section:
    """A named chunk of a song — e.g. ``intro``, ``verse``, ``drop``.

    A section bundles one or more :class:`Pattern` objects that all play together
    for ``bars`` bars whenever the section appears in a :class:`Song`'s sequence.
    """

    name: str
    patterns: list[Pattern] = field(default_factory=list)
    bars: int = 4

    def __post_init__(self) -> None:
        self.bars = max(1, int(self.bars))


@dataclass
class Song:
    """A multi-section arrangement.

    ``sections`` holds the available named chunks; ``sequence`` names the order
    those sections play, by name, so a section can repeat (e.g.
    ``["intro", "verse", "drop", "verse", "drop", "outro"]``).
    """

    bpm: float = 128.0
    sections: list[Section] = field(default_factory=list)
    sequence: list[str] = field(default_factory=list)

    def add_section(self, section: Section) -> Section:
        """Register a section. Returns it for convenient chaining."""
        self.sections.append(section)
        return section

    def _section_map(self) -> dict[str, Section]:
        return {section.name: section for section in self.sections}

    def timeline(self) -> list[tuple[Section, int]]:
        """Resolve ``sequence`` into ``(section, start_bar)`` pairs.

        Sections are laid back-to-back in sequence order, so each entry's start
        bar is the cumulative length of everything before it. A name in
        ``sequence`` that has no matching section raises ``KeyError``.
        """
        by_name = self._section_map()
        resolved: list[tuple[Section, int]] = []
        cursor = 0
        for name in self.sequence:
            section = by_name.get(name)
            if section is None:
                raise KeyError(
                    f"sequence references unknown section {name!r}; "
                    f"defined sections: {sorted(by_name)}"
                )
            resolved.append((section, cursor))
            cursor += section.bars
        return resolved

    @property
    def total_bars(self) -> int:
        """Total length in bars of the whole sequence."""
        by_name = self._section_map()
        total = 0
        for name in self.sequence:
            section = by_name.get(name)
            if section is None:
                raise KeyError(
                    f"sequence references unknown section {name!r}; "
                    f"defined sections: {sorted(by_name)}"
                )
            total += section.bars
        return total

    def to_arrangement(self) -> Arrangement:
        """Flatten the song into a single bar-based :class:`Arrangement`.

        Every pattern of every sequenced section is placed at its absolute start
        bar. Repeated sections produce repeated clips at the right offsets.
        """
        arrangement = Arrangement(bpm=self.bpm)
        for section, start_bar in self.timeline():
            for pattern in section.patterns:
                arrangement.add(pattern, start_bar=start_bar, bars=section.bars)
        return arrangement

    @classmethod
    def from_spec(
        cls,
        bpm: float,
        sections: Mapping[str, Mapping[str, Any]] | list[Section],
        sequence: list[str],
    ) -> Song:
        """Build a :class:`Song` from a lightweight spec.

        ``sections`` may already be :class:`Section` objects, or a mapping of
        ``name -> {"patterns": [...], "bars": int}`` where each pattern is either
        a :class:`Pattern` or a ``(name, dsl)`` pair / DSL string.
        """
        if isinstance(sections, list):
            built = list(sections)
        else:
            built = []
            for name, spec in sections.items():
                raw_patterns = spec.get("patterns", [])
                bars = int(spec.get("bars", 4))
                patterns = [_coerce_pattern(p) for p in raw_patterns]
                built.append(Section(name=name, patterns=patterns, bars=bars))
        return cls(bpm=bpm, sections=built, sequence=list(sequence))


def _coerce_pattern(spec: object) -> Pattern:
    """Coerce a pattern spec into a parsed :class:`Pattern`."""
    if isinstance(spec, Pattern):
        if not spec.steps:
            spec.parse_dsl()
        return spec
    if isinstance(spec, (tuple, list)) and len(spec) == 2:
        pattern = Pattern(name=str(spec[0]), dsl=str(spec[1]))
    else:
        pattern = Pattern(name="pattern", dsl=str(spec))
    pattern.parse_dsl()
    return pattern


def render_song(
    song: Song,
    library: SampleLibrary,
    output_path: Path,
    sample_rate: int = 44100,
) -> Path:
    """Render a :class:`Song` to a stereo WAV file.

    The song's sections are laid out at their absolute bar offsets (per
    ``sequence``) into one :class:`Arrangement`, then rendered with the exact
    same mixing math as :func:`render_arrangement`. Missing/unknown instruments
    are skipped, never fatal; an empty song renders a short silent buffer.
    """
    arrangement = song.to_arrangement()
    mix = _mix_clips(
        arrangement.clips,
        bpm=song.bpm,
        total_bars=song.total_bars,
        sample_library=library,
        sample_rate=sample_rate,
    )
    return _write_mix(mix, output_path, sample_rate)


def render_arrangement(
    arrangement: Arrangement,
    sample_library: SampleLibrary,
    output_path: Path,
    sample_rate: int = 44100,
) -> Path:
    """Render an arrangement to a stereo WAV file.

    This is intentionally offline and conservative. Missing samples are skipped
    rather than crashing, because early audx sessions should stay creative.
    """
    mix = _mix_clips(
        arrangement.clips,
        bpm=arrangement.bpm,
        total_bars=arrangement.total_bars,
        sample_library=sample_library,
        sample_rate=sample_rate,
    )
    return _write_mix(mix, output_path, sample_rate)


def _mix_clips(
    clips: list[Clip],
    bpm: float,
    total_bars: int,
    sample_library: SampleLibrary,
    sample_rate: int,
) -> np.ndarray:
    """Mix a list of clips to a stereo ``float32`` buffer (shared by both renderers).

    Missing/unknown instruments are skipped rather than crashing. This is the
    single source of truth for audx's offline mixing math so that
    :func:`render_arrangement` and :func:`render_song` stay identical.
    """
    seconds_per_beat = 60.0 / bpm
    total_beats = max(4, total_bars * 4)
    total_frames = math.ceil(total_beats * seconds_per_beat * sample_rate)
    mix = np.zeros((total_frames, 2), dtype=np.float32)
    synth_cache: dict[str, np.ndarray] = {}

    for clip in clips:
        for step in clip.pattern.steps:
            data = _voice_audio(step, sample_library, sample_rate, synth_cache)
            if data is None:
                continue
            for bar in range(clip.start_bar, clip.start_bar + clip.bars):
                beat = bar * 4 + clip.pattern.swung_beat(step.beat)
                start = round(beat * seconds_per_beat * sample_rate)
                end = min(start + len(data), total_frames)
                if start >= total_frames or end <= start:
                    continue
                gain = step.velocity * 0.7
                mix[start:end] += data[: end - start] * gain

    return mix


def _write_mix(mix: np.ndarray, output_path: Path, sample_rate: int) -> Path:
    """Peak-normalise (if clipping) and write a stereo mix to ``output_path``."""
    peak = float(np.max(np.abs(mix))) if mix.size else 0.0
    if peak > 1.0:
        mix = mix / peak
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_path), mix, sample_rate)
    return output_path


def _voice_audio(
    step: object,
    sample_library: SampleLibrary,
    sample_rate: int,
    synth_cache: dict[str, np.ndarray],
) -> np.ndarray | None:
    """Resolve a step to stereo ``float32`` audio: real sample, else built-in synth.

    Returns ``None`` when the instrument is neither a known sample nor a synth
    voice, so the renderer can skip it without crashing.
    """
    name = step.sample  # type: ignore[attr-defined]
    tune = getattr(step, "tune_semitones", 0.0)
    sample_path = sample_library.resolve(name)
    if sample_path is not None and sample_path.exists():
        data, source_sr = sf.read(str(sample_path), dtype="float32", always_2d=True)
        if source_sr != sample_rate:
            data = _resample_linear(data, source_sr, sample_rate)
        if data.shape[1] == 1:
            return np.repeat(data, 2, axis=1)
        return data[:, :2]
    if is_synth_voice(name):
        key = f"{name}:{tune}"
        cached = synth_cache.get(key)
        if cached is None:
            mono = synth_voice(name, sample_rate, tune_semitones=tune)
            cached = np.repeat(mono.reshape(-1, 1), 2, axis=1)
            synth_cache[key] = cached
        return cached
    return None


def _resample_linear(data: np.ndarray, source_sr: int, target_sr: int) -> np.ndarray:
    if source_sr == target_sr:
        return data
    ratio = target_sr / source_sr
    target_len = max(1, round(len(data) * ratio))
    old_x = np.linspace(0.0, 1.0, len(data), endpoint=False)
    new_x = np.linspace(0.0, 1.0, target_len, endpoint=False)
    channels = [np.interp(new_x, old_x, data[:, ch]) for ch in range(data.shape[1])]
    return np.stack(channels, axis=1).astype(np.float32)

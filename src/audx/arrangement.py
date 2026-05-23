"""Arrangement model and offline rendering helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

import numpy as np
import soundfile as sf

from audx.pattern import Pattern
from audx.project import Project
from audx.sampler import SampleLibrary


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
    seconds_per_beat = 60.0 / arrangement.bpm
    total_beats = max(4, arrangement.total_bars * 4)
    total_frames = math.ceil(total_beats * seconds_per_beat * sample_rate)
    mix = np.zeros((total_frames, 2), dtype=np.float32)

    for clip in arrangement.clips:
        for step in clip.pattern.steps:
            sample_path = sample_library.resolve(step.sample)
            if sample_path is None or not sample_path.exists():
                continue
            data, source_sr = sf.read(str(sample_path), dtype="float32", always_2d=True)
            if source_sr != sample_rate:
                data = _resample_linear(data, source_sr, sample_rate)
            if data.shape[1] == 1:
                data = np.repeat(data, 2, axis=1)
            else:
                data = data[:, :2]
            for bar in range(clip.start_bar, clip.start_bar + clip.bars):
                beat = bar * 4 + clip.pattern.swung_beat(step.beat)
                start = round(beat * seconds_per_beat * sample_rate)
                end = min(start + len(data), total_frames)
                if start >= total_frames or end <= start:
                    continue
                gain = step.velocity * 0.7
                mix[start:end] += data[: end - start] * gain

    peak = float(np.max(np.abs(mix))) if mix.size else 0.0
    if peak > 1.0:
        mix /= peak
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_path), mix, sample_rate)
    return output_path


def render_project(project_path: Path, output_path: Path, bars: int | None = None, sample_rate: int = 44100) -> Path:
    """Render a saved .audx project using stems relative to the project folder."""
    project_path = Path(project_path)
    project = Project.load(project_path)
    library = SampleLibrary(project_path.parent)
    library.build_index(recursive=True)
    arrangement = Arrangement(bpm=project.bpm)
    render_bars = bars or 4
    for pdata in project.patterns:
        pattern = Pattern(
            name=str(pdata["name"]),
            dsl=str(pdata["dsl"]),
            length_beats=float(pdata.get("length_beats", 4)),
            channel=int(pdata.get("channel", 0)),
            swing=float(pdata.get("swing", 0.0)),
        )
        pattern.parse_dsl()
        arrangement.add(pattern, start_bar=0, bars=render_bars)
    return render_arrangement(arrangement, library, output_path, sample_rate=sample_rate)


def _resample_linear(data: np.ndarray, source_sr: int, target_sr: int) -> np.ndarray:
    if source_sr == target_sr:
        return data
    ratio = target_sr / source_sr
    target_len = max(1, round(len(data) * ratio))
    old_x = np.linspace(0.0, 1.0, len(data), endpoint=False)
    new_x = np.linspace(0.0, 1.0, target_len, endpoint=False)
    channels = [np.interp(new_x, old_x, data[:, ch]) for ch in range(data.shape[1])]
    return cast(np.ndarray, np.stack(channels, axis=1).astype(np.float32))

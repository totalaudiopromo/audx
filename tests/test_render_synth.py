"""Tests for synth-fallback rendering and the demo arrangement."""

from pathlib import Path

import numpy as np
import soundfile as sf

from audx.arrangement import Arrangement, _voice_audio, render_arrangement
from audx.pattern import Pattern
from audx.sampler import SampleLibrary


def _render(dsl: str, tmp_path: Path, name: str = "t", bars: int = 1) -> np.ndarray:
    library = SampleLibrary(tmp_path / "empty")  # no samples → synth fallback
    pattern = Pattern(name=name, dsl=dsl)
    pattern.parse_dsl()
    arr = Arrangement(bpm=120)
    arr.add(pattern, bars=bars)
    out = render_arrangement(arr, library, tmp_path / f"{name}.wav")
    data, _ = sf.read(out, always_2d=True)
    return data


def test_synth_render_makes_sound_without_samples(tmp_path: Path):
    data = _render("kick 4/4", tmp_path)
    assert data.shape[1] == 2
    assert float(np.max(np.abs(data))) > 0.0


def test_unknown_instrument_renders_silence_not_crash(tmp_path: Path):
    # 'wobble' is neither a sample nor a synth voice -> skipped, silent, no crash
    data = _render("wobble 4/4", tmp_path)
    assert float(np.max(np.abs(data))) == 0.0


def test_real_sample_takes_priority_over_synth(tmp_path: Path):
    # A file literally named kick.wav should be used instead of the synth.
    samples = tmp_path / "samples"
    samples.mkdir()
    sf.write(samples / "kick.wav", np.ones((50, 1), dtype=np.float32) * 0.5, 44100)
    library = SampleLibrary(samples)
    library.build_index(recursive=False)
    step = Pattern(name="k", dsl="kick 4/4")
    step.parse_dsl()
    audio = _voice_audio(step.steps[0], library, 44100, {})
    assert audio is not None
    # the constant-0.5 sample is flat; a synth kick is not
    assert np.allclose(audio, 0.5)


def test_voice_audio_returns_none_for_unknown(tmp_path: Path):
    library = SampleLibrary(tmp_path)
    step = Pattern(name="x", dsl="zonk 4/4")
    step.parse_dsl()
    assert _voice_audio(step.steps[0], library, 44100, {}) is None


def test_synth_cache_reused(tmp_path: Path):
    library = SampleLibrary(tmp_path)
    pat = Pattern(name="h", dsl="hh 16x8")
    pat.parse_dsl()
    cache: dict[str, np.ndarray] = {}
    first = _voice_audio(pat.steps[0], library, 44100, cache)
    assert len(cache) == 1  # one entry for the single voice/tune
    second = _voice_audio(pat.steps[1], library, 44100, cache)
    # same cached object reused for the same voice/tune
    assert first is second
    assert len(cache) == 1

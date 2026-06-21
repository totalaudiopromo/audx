"""Tests for the built-in synth kit (audx/synth.py)."""

import numpy as np
import pytest

from audx.synth import (
    SYNTH_VOICES,
    VOICE_ALIASES,
    canonical_voice,
    is_synth_voice,
    list_voices,
    synth_voice,
)


def test_list_voices_matches_canonical():
    assert list_voices() == list(SYNTH_VOICES)
    assert "kick" in SYNTH_VOICES and "snare" in SYNTH_VOICES


@pytest.mark.parametrize("voice", SYNTH_VOICES)
def test_every_voice_renders_audible_buffer(voice):
    buf = synth_voice(voice, 44100)
    assert buf.dtype == np.float32
    assert buf.ndim == 1
    assert len(buf) > 0
    assert np.isfinite(buf).all()
    assert float(np.max(np.abs(buf))) > 0.05  # not silence
    assert float(np.max(np.abs(buf))) <= 1.0  # not clipping past full scale


@pytest.mark.parametrize("alias,target", list(VOICE_ALIASES.items()))
def test_aliases_resolve(alias, target):
    assert canonical_voice(alias) == target
    assert is_synth_voice(alias)


def test_canonical_and_is_synth_for_unknown():
    assert canonical_voice("definitely-not-a-drum") is None
    assert not is_synth_voice("definitely-not-a-drum")


def test_case_insensitive():
    assert canonical_voice("KICK") == "kick"
    assert canonical_voice("BD") == "kick"


def test_velocity_scales_amplitude():
    loud = synth_voice("kick", 44100, velocity=1.0)
    quiet = synth_voice("kick", 44100, velocity=0.25)
    assert float(np.max(np.abs(quiet))) < float(np.max(np.abs(loud)))


def test_velocity_clamped():
    # velocity > 1 is clamped, so it cannot exceed the velocity=1 peak
    full = float(np.max(np.abs(synth_voice("snare", 44100, velocity=1.0))))
    over = float(np.max(np.abs(synth_voice("snare", 44100, velocity=5.0))))
    assert over == pytest.approx(full, rel=1e-6)


def test_tune_down_lengthens_buffer():
    base = synth_voice("kick", 44100, tune_semitones=0.0)
    down = synth_voice("kick", 44100, tune_semitones=-12.0)
    up = synth_voice("kick", 44100, tune_semitones=12.0)
    assert len(down) > len(base) > len(up)


def test_deterministic_with_seed():
    a = synth_voice("hh", 44100, seed=42)
    b = synth_voice("hh", 44100, seed=42)
    assert np.array_equal(a, b)


def test_seed_changes_noise():
    a = synth_voice("hh", 44100, seed=1)
    b = synth_voice("hh", 44100, seed=2)
    assert not np.array_equal(a, b)


def test_sample_rate_affects_length():
    lo = synth_voice("snare", 22050)
    hi = synth_voice("snare", 44100)
    assert len(hi) > len(lo)


def test_unknown_voice_raises():
    with pytest.raises(KeyError):
        synth_voice("nonsense", 44100)

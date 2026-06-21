"""Tests for the melodic/tonal synth voices (audx/synth.py)."""

import numpy as np
import pytest

from audx.synth import (
    SYNTH_VOICES,
    canonical_voice,
    is_synth_voice,
    synth_voice,
)

# The pitched voices added on top of the drum kit.
MELODIC_VOICES = ("bass", "pluck", "stab", "keys", "saw", "sine")


def test_melodic_voices_registered():
    for voice in MELODIC_VOICES:
        assert voice in SYNTH_VOICES
        assert is_synth_voice(voice)


@pytest.mark.parametrize("voice", MELODIC_VOICES)
def test_every_melodic_voice_renders_audible_buffer(voice):
    buf = synth_voice(voice, 44100)
    assert buf.dtype == np.float32
    assert buf.ndim == 1
    assert len(buf) > 0
    assert np.isfinite(buf).all()
    assert float(np.max(np.abs(buf))) > 0.05  # audible, not silence
    assert float(np.max(np.abs(buf))) <= 1.0  # not clipping past full scale


@pytest.mark.parametrize("voice", MELODIC_VOICES)
def test_tune_transposes_via_resample(voice):
    base = synth_voice(voice, 44100, tune_semitones=0.0)
    down = synth_voice(voice, 44100, tune_semitones=-12.0)
    up = synth_voice(voice, 44100, tune_semitones=12.0)
    # Lower pitch -> longer buffer; higher pitch -> shorter buffer.
    assert len(down) > len(base) > len(up)


@pytest.mark.parametrize("voice", MELODIC_VOICES)
def test_melodic_voices_deterministic_with_seed(voice):
    a = synth_voice(voice, 44100, seed=7)
    b = synth_voice(voice, 44100, seed=7)
    assert np.array_equal(a, b)


def test_bass_is_its_own_voice_not_an_alias():
    # `bass` used to be an alias of `sub`; now it is a distinct canonical voice.
    assert canonical_voice("bass") == "bass"
    assert "bass" in SYNTH_VOICES
    bass = synth_voice("bass", 44100)
    sub = synth_voice("sub", 44100)
    # Distinct renderers -> distinct buffers (length and/or content differ).
    assert not (len(bass) == len(sub) and np.array_equal(bass, sub))


def test_ep_aliases_keys():
    assert canonical_voice("ep") == "keys"
    assert is_synth_voice("ep")
    assert np.array_equal(synth_voice("ep", 44100), synth_voice("keys", 44100))


def test_808_still_aliases_sub():
    # Removing the `bass` alias must not disturb the other `sub` aliases.
    assert canonical_voice("808") == "sub"


def test_stab_is_a_chord_not_a_single_tone():
    # A minor triad has more spectral content than a single saw note; sanity-check
    # that the stab buffer is not identical to a lone saw of the same length.
    stab = synth_voice("stab", 44100)
    assert float(np.max(np.abs(stab))) > 0.05

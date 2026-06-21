"""Tests for the live MIDI jam mapping (audx/live.py). Pure logic, no device."""

import pytest

from audx.live import (
    GM_DRUM_NOTES,
    VOICE_CHANNEL,
    note_to_chromatic,
    note_to_drum,
    resolve_note,
)
from audx.synth import SYNTH_VOICES


def test_gm_notes_map_to_real_voices():
    for voice in GM_DRUM_NOTES.values():
        assert voice in SYNTH_VOICES
        assert voice in VOICE_CHANNEL


@pytest.mark.parametrize("note,voice", [(36, "kick"), (38, "snare"), (42, "hh"), (46, "oh")])
def test_known_gm_notes(note, voice):
    assert note_to_drum(note) == (voice, VOICE_CHANNEL[voice])


def test_no_pad_is_silent():
    # every MIDI note across the full range maps to a valid drum voice/channel
    for note in range(128):
        voice, channel = note_to_drum(note)
        assert voice in SYNTH_VOICES
        assert 0 <= channel <= 15


def test_drum_channels_in_range():
    for ch in VOICE_CHANNEL.values():
        assert 0 <= ch <= 15


def test_chromatic_centers_on_middle_c():
    voice, channel, tune = note_to_chromatic(60, "keys")
    assert voice == "keys"
    assert tune == 0.0
    assert 0 <= channel <= 15


def test_chromatic_transposes():
    _, _, up = note_to_chromatic(72, "bass")  # octave up
    _, _, down = note_to_chromatic(48, "bass")  # octave down
    assert up == 12.0
    assert down == -12.0


def test_chromatic_falls_back_for_unknown_voice():
    voice, _, _ = note_to_chromatic(60, "not-a-voice")
    assert voice == "keys"


def test_resolve_note_modes():
    assert resolve_note(36, mode="drums")[0] == "kick"
    v, _ch, tune = resolve_note(64, mode="chromatic", voice="bass")
    assert v == "bass" and tune == 4.0

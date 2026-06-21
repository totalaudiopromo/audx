"""Unit tests for the live finger-drumming pad mapping in the TUI.

These tests exercise the *pure* key→voice mapping only — they never spin up the
Textual event loop, so they stay fast and headless-safe.
"""

from __future__ import annotations

from audx.synth import SYNTH_VOICES, is_synth_voice
from audx.ui.app import SYNTH_PADS, pad_for_key

# Engine channel count (0..15). Mirrors AudioEngine.channels.
MAX_CHANNELS = 16


def test_every_pad_voice_is_a_known_synth_voice() -> None:
    for key, (voice, _channel) in SYNTH_PADS.items():
        assert is_synth_voice(voice), f"pad {key!r} maps to unknown voice {voice!r}"
        # Pads use canonical voice names, so they should be in SYNTH_VOICES directly.
        assert voice in SYNTH_VOICES, f"pad {key!r} voice {voice!r} is not canonical"


def test_pad_channels_in_range() -> None:
    for key, (_voice, channel) in SYNTH_PADS.items():
        assert isinstance(channel, int), f"pad {key!r} channel must be an int"
        assert 0 <= channel < MAX_CHANNELS, f"pad {key!r} channel {channel} out of range"


def test_no_duplicate_channels() -> None:
    channels = [channel for _voice, channel in SYNTH_PADS.values()]
    assert len(channels) == len(set(channels)), "duplicate channel assignments in pads"


def test_no_duplicate_keys_or_voices() -> None:
    # dict keys are unique by construction; assert voices are distinct too so a
    # typo can't silently shadow a pad.
    voices = [voice for voice, _channel in SYNTH_PADS.values()]
    assert len(voices) == len(set(voices)), "duplicate voice assignments in pads"


def test_pads_do_not_collide_with_reserved_keys() -> None:
    # Keys already bound in DAWApp.on_key must not be reused as pads.
    reserved = {"q", "t", "m", "space", ".", "[", "]", "{", "}"} | set("123456789")
    clashes = reserved & set(SYNTH_PADS)
    assert not clashes, f"pad keys collide with reserved bindings: {sorted(clashes)}"


def test_pad_for_key_resolves_mapped_keys() -> None:
    for key, expected in SYNTH_PADS.items():
        assert pad_for_key(key) == expected


def test_pad_for_key_unknown_returns_none() -> None:
    for key in ("q", "t", "1", "space", "Q", "", "ctrl+c"):
        assert pad_for_key(key) is None

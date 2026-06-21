"""Live MIDI jam: play the built-in synth kit from a MIDI controller or Push 2.

This is the real-time "hit a pad, hear a sound" path. Incoming MIDI notes are
mapped to synth voices and triggered on the audio engine immediately, so a kid
mashing pads makes drums instantly — no samples, no project, no setup.

Two modes:

* **drums** (default) — General-MIDI percussion notes map to drum voices
  (note 36 → kick, 38 → snare, 42 → hi-hat …). Any note that isn't a known GM
  drum still makes a sound: it falls back to a drum voice chosen from the note,
  so *every* pad on a Push 2's 8x8 grid triggers something.
* **chromatic** — every note plays one melodic voice (``keys`` by default) at the
  note's pitch, so a keyboard plays melodies and basslines.

The mapping functions here are pure and unit-tested; the audio/MIDI loop needs a
real device and is exercised live.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from audx.synth import SYNTH_VOICES

# Stable mixer channel per drum voice — matches the TUI finger-drum pads so the
# mixer reads the same whether you play from the keyboard or a controller.
VOICE_CHANNEL: dict[str, int] = {
    "kick": 0,
    "snare": 1,
    "clap": 2,
    "hh": 3,
    "oh": 4,
    "rim": 5,
    "tom": 6,
    "cowbell": 7,
    "perc": 8,
    "sub": 9,
    "ride": 10,
    "crash": 11,
    "shaker": 12,
}

# General-MIDI percussion key map (the de-facto standard most pads/Push send).
GM_DRUM_NOTES: dict[int, str] = {
    35: "kick", 36: "kick",
    37: "rim", 39: "clap", 40: "snare", 38: "snare",
    42: "hh", 44: "hh", 46: "oh",
    41: "tom", 43: "tom", 45: "tom", 47: "tom", 48: "tom", 50: "tom",
    49: "crash", 57: "crash", 52: "crash", 55: "crash",
    51: "ride", 59: "ride", 53: "ride",
    56: "cowbell",
    54: "shaker", 70: "shaker", 69: "shaker", 82: "shaker",
    75: "rim", 76: "perc", 77: "perc",
}

# Order used to turn any unmapped note into *some* drum, so no pad is silent.
_FALLBACK_DRUMS: tuple[str, ...] = (
    "kick", "snare", "hh", "clap", "oh", "tom", "rim", "perc", "cowbell", "shaker",
)

CHROMATIC_CENTER = 60  # MIDI middle C == the voice's natural pitch


def note_to_drum(note: int) -> tuple[str, int]:
    """Map a MIDI note to ``(voice, channel)`` for drums mode (never silent)."""
    voice = GM_DRUM_NOTES.get(note)
    if voice is None:
        voice = _FALLBACK_DRUMS[note % len(_FALLBACK_DRUMS)]
    return voice, VOICE_CHANNEL.get(voice, 8)


def note_to_chromatic(note: int, voice: str = "keys") -> tuple[str, int, float]:
    """Map a MIDI note to ``(voice, channel, tune_semitones)`` for chromatic mode."""
    if voice not in SYNTH_VOICES:
        voice = "keys"
    return voice, 14, float(note - CHROMATIC_CENTER)


def resolve_note(
    note: int, mode: str = "drums", voice: str = "keys"
) -> tuple[str, int, float]:
    """Unified mapping → ``(voice, channel, tune_semitones)``."""
    if mode == "chromatic":
        return note_to_chromatic(note, voice)
    v, ch = note_to_drum(note)
    return v, ch, 0.0


def run_jam(
    engine: object,
    port_name: str | None = None,
    mode: str = "drums",
    voice: str = "keys",
    on_trigger: Callable[[int, str, int], None] | None = None,
    pad_layout: dict[int, tuple[str, int, tuple[int, int, int]]] | None = None,
    lights: object | None = None,
) -> None:
    """Open a MIDI input and trigger synth voices live until interrupted.

    ``engine`` must be a started :class:`audx.engine.AudioEngine`. When a
    ``pad_layout`` (e.g. a Push 2 kit) is given, notes in it use that voice/channel
    and, if ``lights`` is provided, the struck pad is flashed. Raises
    ``RuntimeError`` if no MIDI input is available.
    """
    import mido

    from audx.midi import list_inputs

    inputs = list_inputs()
    if not inputs:
        raise RuntimeError("No MIDI input ports found. Connect a controller and retry.")
    chosen = port_name if (port_name and port_name in inputs) else inputs[0]
    port = mido.open_input(chosen)
    try:
        while True:
            for msg in port.iter_pending():
                if msg.type == "note_on" and msg.velocity > 0:
                    if pad_layout is not None and msg.note in pad_layout:
                        v, ch, _rgb = pad_layout[msg.note]
                        tune = 0.0
                    else:
                        v, ch, tune = resolve_note(msg.note, mode=mode, voice=voice)
                    engine.play_synth(  # type: ignore[attr-defined]
                        v, ch, volume=msg.velocity / 127.0, tune_semitones=tune
                    )
                    if lights is not None:
                        lights.flash(msg.note)  # type: ignore[attr-defined]
                    if on_trigger:
                        on_trigger(msg.note, v, msg.velocity)
            if lights is not None:
                lights.tick()  # type: ignore[attr-defined]
            time.sleep(0.002)
    finally:
        port.close()

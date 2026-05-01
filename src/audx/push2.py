"""Push 2 MIDI mapping scaffold.

This is not Ableton Push display/LED integration yet. It is a stable map of
useful control names to MIDI notes/CCs so audx can grow without guessing.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Push2Control:
    name: str
    midi_type: str
    number: int
    description: str


DEFAULT_PUSH2_MAP = [
    Push2Control("play", "note", 85, "Transport play"),
    Push2Control("stop", "note", 86, "Transport stop"),
    Push2Control("record", "note", 87, "Record/arm placeholder"),
    Push2Control("tap_tempo", "note", 3, "Tap tempo"),
    Push2Control("encoder_1", "cc", 14, "Channel 1 gain"),
    Push2Control("encoder_2", "cc", 15, "Channel 2 gain"),
    Push2Control("encoder_3", "cc", 16, "Channel 3 gain"),
    Push2Control("encoder_4", "cc", 17, "Channel 4 gain"),
]


def list_push2_map() -> list[Push2Control]:
    return DEFAULT_PUSH2_MAP.copy()

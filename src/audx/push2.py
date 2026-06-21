"""Push 2 MIDI mapping + pad LED control.

Push 2 lights its pads when you send notes *back* to it: a note-on on channel 0
sets pad ``note`` to the colour at palette index ``velocity``. Exact colours are
defined with a SysEx "set colour palette entry" command and then reapplied. See
Ableton's Push 2 MIDI & Display Interface spec.

This module exposes:
- the original control-name map (``list_push2_map``),
- a drum-kit pad layout (``push2_pad_layout``) used by ``audx jam``,
- ``Push2Lights`` to paint/flash/clear the pads,
- port discovery helpers.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

# Push 2 user SysEx prefix: 00 21 1D (Ableton) 01 (device) 01 (model).
_SYSEX_HEADER = (0x00, 0x21, 0x1D, 0x01, 0x01)
_CMD_SET_PALETTE = 0x03
_CMD_REAPPLY_PALETTE = 0x05

# Pads form an 8x8 grid of notes 36..99; bottom-left = 36, +1 right, +8 up.
PAD_BASE_NOTE = 36
WHITE_INDEX = 122  # palette slot we set to white for the "hit" flash
OFF_INDEX = 0


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


# ── drum-kit pad layout ───────────────────────────────────────────────────────

# Voices laid left→right along the bottom two rows, each a distinct colour so the
# kit is learnable at a glance. RGB 0..255.
PUSH2_PAD_ORDER: tuple[str, ...] = (
    "kick", "snare", "clap", "hh", "oh", "rim", "tom",
    "cowbell", "perc", "sub", "ride", "crash", "shaker",
)
PUSH2_VOICE_COLORS: dict[str, tuple[int, int, int]] = {
    "kick": (255, 80, 24),
    "snare": (255, 196, 40),
    "clap": (255, 64, 156),
    "hh": (40, 220, 230),
    "oh": (36, 210, 168),
    "rim": (170, 230, 64),
    "tom": (232, 150, 48),
    "cowbell": (220, 200, 60),
    "perc": (170, 92, 240),
    "sub": (60, 110, 255),
    "ride": (120, 184, 255),
    "crash": (230, 72, 230),
    "shaker": (92, 220, 96),
}


def push2_pad_layout() -> dict[int, tuple[str, int, tuple[int, int, int]]]:
    """Map Push 2 pad notes → ``(voice, mixer_channel, rgb)`` for the kit."""
    from audx.live import VOICE_CHANNEL

    layout: dict[int, tuple[str, int, tuple[int, int, int]]] = {}
    for i, voice in enumerate(PUSH2_PAD_ORDER):
        note = PAD_BASE_NOTE + i  # 36..48 (bottom two rows)
        layout[note] = (voice, VOICE_CHANNEL[voice], PUSH2_VOICE_COLORS[voice])
    return layout


# ── port discovery ────────────────────────────────────────────────────────────


def find_push2_port(names: list[str], prefer_user: bool = True) -> str | None:
    """Pick a Push 2 port from ``names`` (prefers the 'User' port for LED control)."""
    cands = [n for n in names if "push 2" in n.lower()]
    if not cands:
        return None
    if prefer_user:
        for n in cands:
            if "user" in n.lower():
                return n
    return cands[0]


def push2_input_name() -> str | None:
    import mido

    try:
        return find_push2_port(list(mido.get_input_names()))
    except Exception:  # no MIDI backend (python-rtmidi) installed
        return None


def open_push2_lights() -> Push2Lights | None:
    """Open the Push 2 output for LED control, or ``None`` if not present."""
    import mido

    try:
        name = find_push2_port(list(mido.get_output_names()))
        if name is None:
            return None
        port = mido.open_output(name)
    except Exception:  # no backend / port unavailable
        return None
    return Push2Lights(port)


# ── LED control ───────────────────────────────────────────────────────────────


def _split(value: int) -> tuple[int, int]:
    """8-bit colour value → (low 7 bits, high 1 bit) for Push 2 SysEx."""
    value = max(0, min(255, value))
    return value & 0x7F, (value >> 7) & 0x01


class Push2Lights:
    """Paint, flash and clear Push 2 pads over MIDI.

    ``port`` is any object with a mido-style ``send`` / ``close`` — real hardware
    in use, a fake in tests.
    """

    def __init__(self, port: Any, flash_seconds: float = 0.11):
        self._port = port
        self._flash_seconds = flash_seconds
        self._base: dict[int, int] = {}  # pad note → its palette index
        self._revert: dict[int, float] = {}  # pad note → time to restore colour

    def _sysex(self, *payload: int) -> None:
        import mido

        self._port.send(mido.Message("sysex", data=[*_SYSEX_HEADER, *payload]))

    def set_color(self, index: int, rgb: tuple[int, int, int], white: int = 0) -> None:
        r, g, b = rgb
        self._sysex(
            _CMD_SET_PALETTE, index, *_split(r), *_split(g), *_split(b), *_split(white)
        )

    def reapply(self) -> None:
        self._sysex(_CMD_REAPPLY_PALETTE)

    def _light(self, note: int, index: int) -> None:
        import mido

        self._port.send(mido.Message("note_on", channel=0, note=note, velocity=index))

    def setup(self, layout: dict[int, tuple[str, int, tuple[int, int, int]]]) -> None:
        """Define palette colours for the kit and switch the pads on."""
        self.set_color(OFF_INDEX, (0, 0, 0))
        self.set_color(WHITE_INDEX, (255, 255, 255), white=255)
        self._base.clear()
        for i, (note, (_voice, _ch, rgb)) in enumerate(sorted(layout.items())):
            idx = i + 1  # palette slots 1..N
            self.set_color(idx, rgb)
            self._base[note] = idx
        self.reapply()
        for note, idx in self._base.items():
            self._light(note, idx)

    def flash(self, note: int) -> None:
        """Briefly light a struck pad white; restored by :meth:`tick`."""
        if note in self._base:
            self._light(note, WHITE_INDEX)
            self._revert[note] = time.monotonic() + self._flash_seconds

    def tick(self) -> None:
        """Restore pads whose flash has elapsed (call frequently)."""
        if not self._revert:
            return
        now = time.monotonic()
        for note in [n for n, t in self._revert.items() if now >= t]:
            self._light(note, self._base[note])
            del self._revert[note]

    def clear(self) -> None:
        for note in self._base:
            self._light(note, OFF_INDEX)
        self._revert.clear()

    def close(self) -> None:
        try:
            self.clear()
        finally:
            try:
                self._port.close()
            except Exception:
                pass

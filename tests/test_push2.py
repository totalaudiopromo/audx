"""Tests for Push 2 pad LED control — validates the SysEx/note bytes vs. the spec."""

import pytest

from audx.live import VOICE_CHANNEL
from audx.push2 import (
    OFF_INDEX,
    WHITE_INDEX,
    Push2Lights,
    _split,
    find_push2_port,
    push2_pad_layout,
)
from audx.synth import SYNTH_VOICES


class FakePort:
    """Captures the mido messages a Push2Lights would send to hardware."""

    def __init__(self):
        self.messages = []
        self.closed = False

    def send(self, msg):
        self.messages.append(msg)

    def close(self):
        self.closed = True

    # convenience views
    def sysex(self):
        return [list(m.data) for m in self.messages if m.type == "sysex"]

    def notes(self):
        return [(m.note, m.velocity, m.channel) for m in self.messages if m.type == "note_on"]


def test_split_encoding():
    assert _split(0) == (0, 0)
    assert _split(255) == (127, 1)
    assert _split(200) == (72, 1)


def test_set_color_matches_spec_example():
    # Ableton example: F0 00 21 1D 01 01 03 7D 00 00 00 00 7F 01 7E 00 F7
    # = set palette index 125 to (r=0,g=0,b=255), white=126.
    port = FakePort()
    Push2Lights(port).set_color(125, (0, 0, 255), white=126)
    assert port.sysex() == [
        [0x00, 0x21, 0x1D, 0x01, 0x01, 0x03, 0x7D, 0, 0, 0, 0, 0x7F, 0x01, 0x7E, 0x00]
    ]


def test_reapply_command_bytes():
    port = FakePort()
    Push2Lights(port).reapply()
    assert port.sysex() == [[0x00, 0x21, 0x1D, 0x01, 0x01, 0x05]]


def test_pad_layout_is_valid():
    layout = push2_pad_layout()
    assert len(layout) == 13
    assert set(layout) == set(range(36, 49))  # bottom two rows
    for _note, (voice, channel, rgb) in layout.items():
        assert voice in SYNTH_VOICES
        assert channel == VOICE_CHANNEL[voice]
        assert len(rgb) == 3 and all(0 <= c <= 255 for c in rgb)


def test_setup_paints_and_lights_pads():
    port = FakePort()
    lights = Push2Lights(port)
    lights.setup(push2_pad_layout())
    # one note_on per pad to switch it on, none off yet
    notes = port.notes()
    assert len(notes) == 13
    assert all(ch == 0 and vel > 0 for _, vel, ch in notes)


def test_flash_then_tick_restores():
    port = FakePort()
    lights = Push2Lights(port, flash_seconds=0.0)  # revert immediately
    lights.setup(push2_pad_layout())
    base_count = len(port.notes())
    lights.flash(36)  # kick pad
    lights.tick()
    notes = port.notes()
    # flash sent white, tick restored the base colour → two extra note_ons
    assert len(notes) == base_count + 2
    assert notes[base_count][1] == WHITE_INDEX


def test_flash_ignores_unmapped_pad():
    port = FakePort()
    lights = Push2Lights(port)
    lights.setup(push2_pad_layout())
    before = len(port.notes())
    lights.flash(99)  # not in the kit
    assert len(port.notes()) == before


def test_clear_turns_pads_off():
    port = FakePort()
    lights = Push2Lights(port)
    lights.setup(push2_pad_layout())
    port.messages.clear()
    lights.clear()
    assert all(vel == OFF_INDEX for _, vel, _ in port.notes())


def test_close_clears_and_closes():
    port = FakePort()
    lights = Push2Lights(port)
    lights.setup(push2_pad_layout())
    lights.close()
    assert port.closed


@pytest.mark.parametrize(
    "names,expected",
    [
        (["Ableton Push 2 Live Port", "Ableton Push 2 User Port"], "Ableton Push 2 User Port"),
        (["Ableton Push 2"], "Ableton Push 2"),
        (["MPK Mini", "Launchkey"], None),
    ],
)
def test_find_push2_port_prefers_user(names, expected):
    assert find_push2_port(names) == expected

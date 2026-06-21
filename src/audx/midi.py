"""MIDI output, clock-out, and input recording (spec §11)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

import mido

from audx.pattern import Pattern


def list_outputs() -> list[str]:
    try:
        return list(mido.get_output_names())
    except Exception:
        return []


def list_inputs() -> list[str]:
    try:
        return list(mido.get_input_names())
    except Exception:
        return []


class MidiOutput:
    """Send note + control messages to a single MIDI output."""

    def __init__(self, port_name: str | None = None):
        ports = list_outputs()
        if port_name and port_name in ports:
            self.port = mido.open_output(port_name)
        elif ports:
            self.port = mido.open_output(ports[0])
        else:
            self.port = None

    def send_note(self, note: int, velocity: int = 100, channel: int = 0, duration: float = 0.1) -> None:
        if self.port is None:
            return
        self.port.send(mido.Message("note_on", channel=channel, note=note, velocity=velocity))
        self.port.send(mido.Message("note_off", channel=channel, note=note))

    def close(self) -> None:
        if self.port is not None:
            try:
                self.port.close()
            except Exception:
                pass


class MidiClock:
    """Send 24 PPQN clock + start/stop messages so external gear locks to audx.

    Threaded so the audio path never sees clock work. Stop with ``.stop()``.
    """

    def __init__(self, bpm: float = 128.0, port_name: str | None = None) -> None:
        self.bpm = bpm
        self.port_name = port_name
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.port: Any = None  # mido output port (untyped); created on start()

    def start(self) -> None:
        ports = list_outputs()
        if self.port_name and self.port_name in ports:
            self.port = mido.open_output(self.port_name)
        elif ports:
            self.port = mido.open_output(ports[0])
        else:
            self.port = None
            return
        self.port.send(mido.Message("start"))
        self._stop.clear()
        self._thread = threading.Thread(target=self._tick, daemon=True, name="audx-midi-clock")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        if self.port is not None:
            try:
                self.port.send(mido.Message("stop"))
                self.port.close()
            except Exception:
                pass
        self.port = None

    def _tick(self) -> None:
        # 24 PPQN: one clock every (60 / bpm / 24) seconds.
        interval = 60.0 / max(1.0, self.bpm) / 24.0
        next_tick = time.monotonic()
        while not self._stop.is_set():
            try:
                if self.port is not None:
                    self.port.send(mido.Message("clock"))
            except Exception:
                return
            next_tick += interval
            sleep_for = next_tick - time.monotonic()
            if sleep_for > 0:
                self._stop.wait(sleep_for)


@dataclass
class RecordedNote:
    note: int
    velocity: int
    beat: float
    duration: float


def record_midi(
    port_name: str | None = None,
    bars: int = 1,
    bpm: float = 128.0,
    quantize: int | None = 16,
) -> list[RecordedNote]:
    """Record incoming MIDI for ``bars`` bars and return note events.

    ``quantize=16`` snaps to 16th-note grid; pass ``None`` to keep human timing.
    """
    inputs = list_inputs()
    if port_name and port_name in inputs:
        port = mido.open_input(port_name)
    elif inputs:
        port = mido.open_input(inputs[0])
    else:
        return []

    seconds_per_beat = 60.0 / bpm
    duration_s = bars * 4 * seconds_per_beat
    start = time.monotonic()
    pending: dict[int, tuple[float, int]] = {}
    notes: list[RecordedNote] = []
    try:
        while True:
            now = time.monotonic()
            elapsed = now - start
            if elapsed >= duration_s:
                break
            for message in port.iter_pending():
                t = (now - start) / seconds_per_beat
                if message.type == "note_on" and message.velocity > 0:
                    pending[message.note] = (t, message.velocity)
                elif message.type in ("note_off", "note_on"):
                    on = pending.pop(message.note, None)
                    if on is not None:
                        beat, velocity = on
                        if quantize:
                            grid = 4.0 / quantize
                            beat = round(beat / grid) * grid
                        notes.append(RecordedNote(message.note, velocity, beat, max(0.05, t - on[0])))
            time.sleep(0.005)
    finally:
        port.close()
    return notes


def notes_to_pattern(notes: list[RecordedNote], name: str = "rec", channel: int = 0) -> Pattern:
    """Convert recorded notes to an explicit-grid Pattern."""
    if not notes:
        return Pattern(name=name, dsl="[0]", channel=channel)
    grid_size = 16
    grid = ["0"] * grid_size
    for note in notes:
        idx = round((note.beat % 4.0) / (4.0 / grid_size)) % grid_size
        grid[idx] = "1"
    pattern = Pattern(name=name, dsl=f"[{'.'.join(grid)}] | channel {channel}", channel=channel)
    pattern.parse_dsl()
    return pattern

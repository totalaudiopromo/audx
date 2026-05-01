"""
MIDI output support (Push 2 as generic MIDI controller, external synths).
"""
import mido
from typing import Optional

class MidiOutput:
    def __init__(self, port_name: Optional[str] = None):
        ports = mido.get_output_names()
        if port_name:
            self.port = mido.open_output(port_name)
        elif ports:
            self.port = mido.open_output(ports[0])
        else:
            self.port = None

    def send_note(self, note: int, velocity: int = 100, channel: int = 0, duration: float = 0.1):
        if self.port:
            self.port.send(mido.Message('note_on', channel=channel, note=note, velocity=velocity))
            # schedule note_off (in real code use a scheduler thread)
            self.port.send(mido.Message('note_off', channel=channel, note=note))

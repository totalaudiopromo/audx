"""
16-channel mixer with per-channel level, pan, sends, and master output.
"""
from typing import TYPE_CHECKING, List, Optional

import numpy as np

if TYPE_CHECKING:
    from audx.audio.voice import Voice

class Channel:
    """One mixer strip."""
    def __init__(self, name: str = ""):
        self.name = name
        self.level = 0.8  # 0..1 linear pre-fader
        self.pan = 0.0    # -1 L .. +1 R
        self.mute = False
        self.solo = False
        self.sends = [0.0, 0.0]  # two aux sends (future)
        self.insert_gain = 1.0
        self._voices: List['Voice'] = []

    def add_voice(self, voice):
        self._voices.append(voice)

    def remove_finished(self):
        self._voices = [v for v in self._voices if not v.is_finished]

class Mixer:
    """16-channel stereo mixer with master output."""
    def __init__(self, channels: int = 16, sample_rate: int = 44100):
        self.channels = [Channel(f"CH{i+1}") for i in range(channels)]
        self.master_level = 0.8
        self.master_limiter_threshold = 0.99
        self.sample_rate = sample_rate

    def process(self, frames: int) -> np.ndarray:
        """
        Mix all active voices across channels into stereo output.
        Returns float32 interleaved array.
        """
        mixed = np.zeros(frames * 2, dtype=np.float32)  # stereo interleaved
        for ch in self.channels:
            if ch.mute:
                continue
            ch.remove_finished()
            for voice in ch._voices:
                # Per-channel pan & level
                voice_gain = ch.level * ch.insert_gain
                voice.gain = voice_gain
                voice.pan = ch.pan
                ch_signal = voice.process(frames)
                # Accumulate
                mixed += ch_signal
        # Master gain
        mixed *= self.master_level
        # Simple hard limiter (soft clamp)
        np.clip(mixed, -self.master_limiter_threshold, self.master_limiter_threshold, out=mixed)
        return mixed

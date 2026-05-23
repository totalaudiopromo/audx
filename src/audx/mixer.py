"""16-channel mixer with levels, pan, mute/solo."""

import numpy as np

from .engine import get_engine


class Mixer:
    def __init__(self, channels: int = 16):
        self.channels = channels
        # Fader: 0.0 to 2.0 linear (0dB=1.0), start at 0.8 (~-2dB)
        self.levels = np.ones(channels, dtype=np.float32) * 0.8
        self.pan = np.zeros(channels, dtype=np.float32)        # -1 L, +1 R
        self.mute = np.zeros(channels, dtype=bool)
        self.solo = np.zeros(channels, dtype=bool)
        self.solo_active = False

    def set_level(self, ch: int, db: float):
        if db <= -90:
            lin = 0.0
        else:
            lin = 10 ** (db / 20)
        self.levels[ch] = np.clip(lin, 0.0, 2.0)

    def get_level(self, ch: int) -> float:
        return float(self.levels[ch])

    def set_pan(self, ch: int, pan: float):
        self.pan[ch] = np.clip(pan, -1, 1)

    def toggle_mute(self, ch: int):
        self.mute[ch] = not self.mute[ch]

    def toggle_solo(self, ch: int):
        self.solo[ch] = not self.solo[ch]

    def apply_to_engine(self):
        engine = get_engine()
        if not engine:
            return
        for ch in range(self.channels):
            if self.mute[ch] or (self.solo_active and not self.solo[ch]):
                engine.set_channel_pan(ch, 0)  # silence via pan (muted channel)
            else:
                engine.set_channel_pan(ch, self.pan[ch])

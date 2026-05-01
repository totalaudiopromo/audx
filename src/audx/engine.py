"""
audx — Core audio engine.

Handles:
- Audio backend (sounddevice / CoreAudio)
- Sample playback voices (memory-mapped WAV/FLAC/MP3)
- Mix bus (16 channels)
- Real-time thread with low-latency callback
"""

import threading

import numpy as np
import sounddevice as sd
import soundfile as sf

from audx.pattern import get_pattern_engine
from audx.sampler import get_sample_library


class AudioEngine:
    """Main audio engine — runs a real-time audio callback."""
    def __init__(self, sample_rate: int = 48000, buffer_size: int = 256):
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.stream: sd.Stream | None = None
        self.running = False
        self.lock = threading.RLock()
        self.channels = 16
        self.mix_buffer = np.zeros((self.channels, buffer_size), dtype=np.float32)
        self.channel_levels = np.zeros(self.channels, dtype=np.float32)
        self.channel_pan = np.zeros(self.channels, dtype=np.float32)    # -1=L, +1=R
        self.channel_mute = np.zeros(self.channels, dtype=bool)
        self.channel_gain = np.ones(self.channels, dtype=np.float32)
        self.master_level = 1.0
        self.scheduler_callback = None
        self.active_voices: list[Voice] = []
        self.pattern_engine = get_pattern_engine()
        self.sample_library = get_sample_library()
        # BPM set from config at runtime  # default, will be set from config


    def start(self):
        if self.stream and self.stream.active:
            return
        self.stream = sd.Stream(
            samplerate=self.sample_rate,
            blocksize=self.buffer_size,
            channels=2,
            dtype='float32',
            callback=self._audio_callback,
            finished_callback=self._stream_finished
        )
        self.stream.start()
        self.running = True

    def stop(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        self.running = False

    def _audio_callback(self, indata, outdata, frames, time_info, status):
        if status:
            print(f"[Audio] {status}")
        self.mix_buffer[:] = 0.0
        # Advance pattern scheduler
        delta_time = frames / self.sample_rate
        pattern_steps = self.pattern_engine.tick(delta_time)
        for step in pattern_steps:
            # Resolve sample path using global sample library
            sample_path = self.sample_library.resolve(step.sample)
            if sample_path and sample_path.exists():
                ch = step.metadata.get('channel', 0)
                ch = max(0, min(int(ch), self.channels - 1))
                velocity = step.velocity
                voice = SampleVoice(str(sample_path), channel=ch, gain=velocity, pan=0.0)
                with self.lock:
                    self.active_voices.append(voice)
            else:
                print(f"[WARN] Sample not found: {step.sample}")

        with self.lock:
            alive = []
            for voice in self.active_voices:
                if voice.is_active:
                    samples = voice.generate(frames, self.sample_rate)
                    ch = voice.channel
                    if not self.channel_mute[ch]:
                        gain = voice.gain * float(self.channel_gain[ch])
                        self.mix_buffer[ch, :] += samples * gain
                    alive.append(voice)
            self.active_voices = alive
            for ch in range(self.channels):
                self.channel_levels[ch] = np.sqrt(np.mean(self.mix_buffer[ch]**2)) if frames > 0 else 0.0
        mono = np.sum(self.mix_buffer, axis=0) * self.master_level
        outdata[:, 0] = mono * 0.7
        outdata[:, 1] = mono * 0.7

    def _stream_finished(self):
        self.running = False

    def play_sample(self, sample_path: str, channel: int, volume: float = 1.0, pan: float = 0.0, **kwargs):
        with self.lock:
            voice = SampleVoice(sample_path, channel, volume, pan, **kwargs)
            self.active_voices.append(voice)
        return voice

    def set_channel_gain(self, channel: int, gain: float):
        with self.lock:
            self.channel_gain[channel] = np.clip(gain, 0.0, 2.0)

    def set_channel_pan(self, channel: int, pan: float):
        with self.lock:
            self.channel_pan[channel] = np.clip(pan, -1, 1)

    def set_master(self, level: float):
        with self.lock:
            self.master_level = np.clip(level, 0.0, 2.0)

    def set_bpm(self, bpm: float):
        with self.lock:
            self.bpm = bpm
        self.pattern_engine.set_bpm(bpm)

    def get_channel_levels(self) -> np.ndarray:
        with self.lock:
            return self.channel_levels.copy()


class Voice:
    def __init__(self, channel: int, gain: float = 1.0, pan: float = 0.0):
        self.channel = channel
        self.gain = gain
        self.pan = pan
        self.position = 0
        self.is_active = True

    def generate(self, frames: int, sr: int) -> np.ndarray:
        raise NotImplementedError


class SampleVoice(Voice):
    def __init__(self, sample_path: str, channel: int, gain: float, pan: float, **kwargs):
        super().__init__(channel, gain, pan)
        self.sample_path = sample_path
        self.loop = kwargs.get('loop', False)
        self.start_frame = kwargs.get('start_frame', 0)
        try:
            self.data, self.sr = sf.read(sample_path, dtype='float32', always_2d=False)
            if self.data.ndim > 1:
                self.data = np.mean(self.data, axis=1)
            self.data = self.data.astype(np.float32)
            self.position = self.start_frame
            self.length = len(self.data)
            print(f"  ▶ Playing {sample_path.split('/')[-1]} on ch{channel+1}")
        except Exception as e:
            print(f"  ✗ Failed to load sample: {e}")
            self.is_active = False
            self.data = np.zeros(1, dtype=np.float32)

    def generate(self, frames: int, sr: int) -> np.ndarray:
        if not self.is_active:
            return np.zeros(frames, dtype=np.float32)
        end_pos = self.position + frames
        if end_pos <= self.length:
            block = self.data[self.position:end_pos]
            self.position = end_pos
            if self.loop and end_pos >= self.length:
                self.position = 0
        else:
            remaining = self.length - self.position
            block = np.zeros(frames, dtype=np.float32)
            if remaining > 0:
                block[:remaining] = self.data[self.position:]
            self.is_active = False
        return block


_engine: AudioEngine | None = None

def get_engine() -> AudioEngine | None:
    global _engine
    return _engine

def init_engine(sample_rate=None, buffer_size=None) -> AudioEngine:
    global _engine
    if _engine is None:
        from audx.config import AUDX_BPM
        # Use defaults if not provided
        sr = sample_rate or 48000
        bs = buffer_size or 256
        _engine = AudioEngine(sr, bs)
        _engine.set_bpm(float(AUDX_BPM))
    return _engine

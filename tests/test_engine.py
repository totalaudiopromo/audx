"""Tests for audio engine basic operations."""

import numpy as np
import soundfile as sf

from audx.engine import AudioEngine
from audx.pattern import Pattern
from audx.sampler import SampleLibrary


def test_engine_creation():
    engine = AudioEngine()
    assert engine.sample_rate == 48000
    assert engine.channels == 16
    assert engine.master_level == 1.0
    assert np.allclose(engine.channel_gain, np.ones(16))


def test_engine_set_bpm():
    engine = AudioEngine()
    engine.set_bpm(140.0)
    assert engine.bpm == 140.0
    assert engine.pattern_engine.bpm == 140.0


def test_engine_channel_gain():
    engine = AudioEngine()
    engine.set_channel_gain(0, 1.5)
    engine.set_channel_gain(1, 3.0)
    assert engine.channel_gain[0] == 1.5
    assert engine.channel_gain[1] == 2.0


def test_engine_voice_lifecycle():
    engine = AudioEngine()
    assert not engine.running


def test_audio_callback_routes_pattern_steps_to_declared_channel(tmp_path):
    sample_path = tmp_path / "kick.wav"
    sf.write(sample_path, np.ones((512, 1), dtype=np.float32) * 0.4, 48000)

    library = SampleLibrary(tmp_path)
    library.build_index(recursive=False)

    engine = AudioEngine()
    engine.sample_library = library
    engine.pattern_engine.patterns.clear()
    pattern = Pattern(name="kick", dsl="kick 4/4 | channel 2")
    pattern.parse_dsl()
    engine.pattern_engine.add_pattern(pattern)
    engine.pattern_engine.start()

    outdata = np.zeros((engine.buffer_size, 2), dtype=np.float32)
    engine._audio_callback(outdata, engine.buffer_size, {}, None)

    assert engine.channel_levels[2] > 0
    assert engine.channel_levels[0] == 0

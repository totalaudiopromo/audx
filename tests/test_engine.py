"""Tests for audio engine basic operations."""

import numpy as np

from audx.engine import AudioEngine


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

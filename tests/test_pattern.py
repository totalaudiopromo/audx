"""Tests for pattern DSL and scheduler."""

import random

from audx.pattern import MarkovChain, Pattern, PatternEngine, euclidean_rhythm


def test_pattern_parsing_xo():
    pattern = Pattern(name="kick", dsl="x--- -x-- --x- ---x")
    pattern.parse_dsl()
    assert len(pattern.steps) == 4
    assert pattern.steps[0].sample == "kick"
    assert [round(step.beat, 2) for step in pattern.steps] == [0.0, 1.25, 2.5, 3.75]


def test_pattern_parsing_kick_44():
    pattern = Pattern(name="kick", dsl="kick 4/4 | vel 0.7 | channel 2")
    pattern.parse_dsl()
    assert len(pattern.steps) == 4
    assert all(step.sample == "kick" for step in pattern.steps)
    assert all(step.velocity == 0.7 for step in pattern.steps)
    assert all(step.channel == 2 for step in pattern.steps)


def test_pattern_engine_accumulates_audio_callbacks():
    engine = PatternEngine(bpm=120.0)
    pattern = Pattern(name="kick", dsl="kick 4/4")
    pattern.parse_dsl()
    engine.add_pattern(pattern)
    engine.start()

    steps = []
    # 256 frames at 48k is ~5.3ms. The old scheduler never advanced because
    # each callback was smaller than a 16th note. This simulates one bar.
    for _ in range(374):
        steps.extend(engine.tick(256 / 48000))

    assert len(steps) == 4
    assert all(step.sample == "kick" for step in steps)


def test_pattern_swing_delays_off_grid_steps():
    pattern = Pattern(name="hh", dsl="hh 16x8 | swing 50%")
    pattern.parse_dsl()
    assert pattern.swing == 0.5
    assert pattern.swung_beat(0.25) == 0.375

    engine = PatternEngine(bpm=60.0)
    engine.add_pattern(pattern)
    engine.start()
    first = engine.tick(0.0)
    before_swing = engine.tick(0.30)
    after_swing = engine.tick(0.08)
    assert len(first) == 1
    assert before_swing == []
    assert len(after_swing) == 1


def test_euclidean_rhythm_generates_hits():
    pattern = euclidean_rhythm(3, 8, sample="rim")
    assert len(pattern.steps) == 3
    assert all(step.sample == "rim" for step in pattern.steps)


def test_pattern_dsl_euclidean_notation():
    pattern = Pattern(name="perc", dsl="perc e(5,16,2)")
    pattern.parse_dsl()
    assert len(pattern.steps) == 5
    assert all(step.sample == "percussion" for step in pattern.steps)


def test_pattern_dsl_explicit_grid():
    pattern = Pattern(name="clap", dsl="clap [1.0.1.0.1.1.0.0]")
    pattern.parse_dsl()
    assert len(pattern.steps) == 4


def test_pattern_dsl_two_eighth_lands_on_beats_2_and_4():
    pattern = Pattern(name="snare", dsl="snare 2/8")
    pattern.parse_dsl()
    beats = sorted(step.beat for step in pattern.steps)
    assert beats == [1.0, 3.0]


def test_pattern_dsl_gain_pan_tune_propagate_to_steps():
    pattern = Pattern(name="kick", dsl="kick 4/4 | gain -3db | pan L50 | tune -2st")
    pattern.parse_dsl()
    assert pattern.gain_db == -3.0
    assert pattern.pan == -0.5
    assert pattern.tune_semitones == -2.0
    assert all(step.gain_db == -3.0 for step in pattern.steps)
    assert all(step.pan == -0.5 for step in pattern.steps)


def test_pattern_dsl_chance_drops_steps_probabilistically():
    pattern = Pattern(name="hh", dsl="hh 16x8 | chance 0%")
    pattern.parse_dsl()
    assert pattern.chance == 0.0
    engine = PatternEngine(bpm=60.0)
    engine.add_pattern(pattern)
    engine.start()
    fired: list = []
    for _ in range(20):
        fired.extend(engine.tick(0.25))
    assert fired == []


def test_pattern_dsl_humanize_jitters_velocity():
    random.seed(7)
    pattern = Pattern(name="kick", dsl="kick 4/4 | humanize 100%")
    pattern.parse_dsl()
    engine = PatternEngine(bpm=60.0)
    engine.add_pattern(pattern)
    engine.start()
    fired: list = []
    for _ in range(8):
        fired.extend(engine.tick(0.5))
    velocities = {round(step.velocity, 3) for step in fired}
    assert len(velocities) > 1


def test_markov_chain_from_sequence():
    chain = MarkovChain.from_sequence(["kick", "-", "snare", "-"])
    pattern = chain.generate_pattern(length=8)
    assert len(pattern.steps) <= 8

"""Tests for the Song / multi-section arrangement model and rendering."""

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from audx.arrangement import Section, Song, render_song
from audx.pattern import Pattern
from audx.sampler import SampleLibrary


def _pattern(name: str, dsl: str) -> Pattern:
    pattern = Pattern(name=name, dsl=dsl)
    pattern.parse_dsl()
    return pattern


def _song() -> Song:
    intro = Section(name="intro", patterns=[_pattern("hh", "hh 16x8")], bars=2)
    verse = Section(
        name="verse",
        patterns=[_pattern("kick", "kick 4/4"), _pattern("hh", "hh 16x8")],
        bars=4,
    )
    drop = Section(name="drop", patterns=[_pattern("kick", "kick 4/4")], bars=8)
    outro = Section(name="outro", patterns=[_pattern("hh", "hh 8x8")], bars=2)
    song = Song(bpm=120, sections=[intro, verse, drop, outro])
    song.sequence = ["intro", "verse", "drop", "verse", "drop", "outro"]
    return song


def test_add_section_registers_and_returns():
    song = Song(bpm=128)
    section = Section(name="intro", bars=4)
    returned = song.add_section(section)
    assert returned is section
    assert song.sections == [section]


def test_timeline_resolves_absolute_bar_offsets():
    song = _song()
    timeline = song.timeline()
    names = [section.name for section, _ in timeline]
    offsets = [start for _, start in timeline]
    assert names == ["intro", "verse", "drop", "verse", "drop", "outro"]
    # intro 2, verse 4, drop 8, verse 4, drop 8, outro 2
    assert offsets == [0, 2, 6, 14, 18, 26]


def test_total_bars_matches_sequence_with_repeats():
    song = _song()
    assert song.total_bars == 2 + 4 + 8 + 4 + 8 + 2  # == 28


def test_to_arrangement_places_every_pattern_at_offsets():
    song = _song()
    arrangement = song.to_arrangement()
    # intro:1 + verse:2 + drop:1 + verse:2 + drop:1 + outro:1 patterns
    assert len(arrangement.clips) == 8
    assert arrangement.total_bars == 28
    # the verse kick that starts the second verse sits at bar 14
    starts = sorted({clip.start_bar for clip in arrangement.clips})
    assert starts == [0, 2, 6, 14, 18, 26]


def test_render_song_writes_stereo_wav_with_matching_duration(tmp_path: Path):
    song = _song()
    library = SampleLibrary(tmp_path / "empty")  # no samples → synth voices
    out = render_song(song, library, tmp_path / "song.wav")
    assert out.exists()

    data, sr = sf.read(out, always_2d=True)
    assert sr == 44100
    assert data.shape[1] == 2

    seconds_per_beat = 60.0 / song.bpm
    expected_beats = song.total_bars * 4
    expected_frames = round(expected_beats * seconds_per_beat * sr)
    # frame count tracks total_bars at the given bpm (rounding tolerance)
    assert abs(data.shape[0] - expected_frames) <= 2
    # synth voices actually make sound
    assert float(np.max(np.abs(data))) > 0.0


def test_render_song_with_unknown_instrument_does_not_crash(tmp_path: Path):
    section = Section(name="a", patterns=[_pattern("wobble", "wobble 4/4")], bars=2)
    song = Song(bpm=120, sections=[section], sequence=["a"])
    library = SampleLibrary(tmp_path / "empty")
    out = render_song(song, library, tmp_path / "silent.wav")
    data, _ = sf.read(out, always_2d=True)
    assert float(np.max(np.abs(data))) == 0.0


def test_sequence_referencing_undefined_section_raises():
    song = Song(bpm=120, sections=[Section(name="intro", bars=2)])
    song.sequence = ["intro", "chorus"]  # 'chorus' not defined
    with pytest.raises(KeyError, match="chorus"):
        song.timeline()
    with pytest.raises(KeyError, match="chorus"):
        _ = song.total_bars


def test_empty_song_renders_without_crashing(tmp_path: Path):
    song = Song(bpm=120)
    assert song.total_bars == 0
    assert song.timeline() == []
    library = SampleLibrary(tmp_path / "empty")
    out = render_song(song, library, tmp_path / "empty.wav")
    data, _ = sf.read(out, always_2d=True)
    assert data.shape[1] == 2
    # falls back to the minimum 4-beat silent buffer, no exception
    assert float(np.max(np.abs(data))) == 0.0


def test_from_spec_builds_equivalent_song(tmp_path: Path):
    song = Song.from_spec(
        bpm=120,
        sections={
            "intro": {"patterns": [("hh", "hh 16x8")], "bars": 2},
            "drop": {"patterns": [_pattern("kick", "kick 4/4")], "bars": 4},
        },
        sequence=["intro", "drop", "drop"],
    )
    assert song.total_bars == 2 + 4 + 4
    assert [s.name for s, _ in song.timeline()] == ["intro", "drop", "drop"]
    library = SampleLibrary(tmp_path / "empty")
    out = render_song(song, library, tmp_path / "spec.wav")
    data, _ = sf.read(out, always_2d=True)
    assert float(np.max(np.abs(data))) > 0.0

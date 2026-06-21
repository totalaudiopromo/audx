"""Additional coverage: MIDI export, project round-trips, DSL operators, CLI."""

from pathlib import Path

import mido
import pytest
from typer.testing import CliRunner

from audx.cli import app
from audx.midi_export import patterns_to_midi
from audx.pattern import Pattern, get_pattern_engine
from audx.project import Project, get_template, init_project

runner = CliRunner()


@pytest.fixture(autouse=True)
def _reset_engine_state():
    get_pattern_engine().patterns.clear()
    yield
    get_pattern_engine().patterns.clear()


# ── MIDI export ────────────────────────────────────────────────────────────────


def test_patterns_to_midi_writes_notes(tmp_path: Path):
    pat = Pattern(name="kick", dsl="kick 4/4")
    pat.parse_dsl()
    out = patterns_to_midi({"kick": pat}, tmp_path / "k.mid", bpm=120, bars=1)
    assert out.exists()
    mid = mido.MidiFile(out)
    note_ons = [m for track in mid.tracks for m in track if m.type == "note_on"]
    assert len(note_ons) >= 4  # four-on-the-floor


def test_midi_tempo_roundtrip(tmp_path: Path):
    pat = Pattern(name="snare", dsl="snare 2/8")
    pat.parse_dsl()
    out = patterns_to_midi({"snare": pat}, tmp_path / "s.mid", bpm=90)
    mid = mido.MidiFile(out)
    tempos = [m for track in mid.tracks for m in track if m.type == "set_tempo"]
    assert tempos
    assert round(mido.tempo2bpm(tempos[0].tempo)) == 90


# ── Project round-trips ─────────────────────────────────────────────────────────


def test_project_save_load_roundtrip(tmp_path: Path):
    proj = Project(name="demo", bpm=140, patterns=[{"name": "k", "dsl": "kick 4/4"}])
    path = tmp_path / "demo.audx"
    proj.save(path)
    loaded = Project.load(path)
    assert loaded.name == "demo"
    assert loaded.bpm == 140
    assert loaded.patterns[0]["name"] == "k"


@pytest.mark.parametrize("template", ["empty", "techno", "hip-hop", "demo"])
def test_templates_build(template):
    proj = get_template(template)
    assert isinstance(proj, Project)
    assert proj.bpm > 0


def test_init_project_layout(tmp_path: Path):
    path = init_project(name="song", parent=tmp_path, template="techno", git=False)
    assert path.exists()
    assert (path.parent / "stems").is_dir()
    assert (path.parent / "renders").is_dir()


def test_init_project_rejects_duplicate(tmp_path: Path):
    init_project(name="dup", parent=tmp_path, template="empty", git=False)
    with pytest.raises(FileExistsError):
        init_project(name="dup", parent=tmp_path, template="empty", git=False)


# ── DSL operators ──────────────────────────────────────────────────────────────


def test_euclidean_hit_count():
    pat = Pattern(name="p", dsl="perc e(5,16)")
    pat.parse_dsl()
    assert len(pat.steps) == 5


def test_euclidean_rotation_changes_first_hit():
    a = Pattern(name="a", dsl="perc e(5,16,0)")
    a.parse_dsl()
    b = Pattern(name="b", dsl="perc e(5,16,2)")
    b.parse_dsl()
    assert [s.beat for s in a.steps] != [s.beat for s in b.steps]


def test_explicit_grid():
    pat = Pattern(name="c", dsl="clap [1.0.1.0.1.1.0.0]")
    pat.parse_dsl()
    assert len(pat.steps) == 4


def test_velocity_modifier():
    pat = Pattern(name="h", dsl="hh 16x8 | vel 0.45")
    pat.parse_dsl()
    assert all(abs(s.velocity - 0.45) < 1e-6 for s in pat.steps)


def test_channel_modifier():
    pat = Pattern(name="h", dsl="hh 16x8 | channel 3")
    pat.parse_dsl()
    assert all(s.channel == 3 for s in pat.steps)


def test_swing_offsets_odd_steps():
    pat = Pattern(name="h", dsl="hh 16x8 | swing 50%")
    pat.parse_dsl()
    assert pat.swing > 0


def test_xrest_grid():
    pat = Pattern(name="g", dsl="x--- -x-- --x- ---x")
    pat.parse_dsl()
    assert len(pat.steps) == 4


def test_empty_dsl_no_steps():
    pat = Pattern(name="e", dsl="")
    pat.parse_dsl()
    assert pat.steps == []


# ── More CLI surface ───────────────────────────────────────────────────────────


def test_fork_project(tmp_path: Path):
    src = init_project(name="orig", parent=tmp_path, template="empty", git=False)
    result = runner.invoke(app, ["fork", str(src.parent), "forked"])
    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "forked" / "project.audx").exists()


def test_watch_once(tmp_path: Path):
    src = init_project(name="w", parent=tmp_path, template="techno", git=False)
    result = runner.invoke(app, ["watch", str(src), "--once"])
    assert result.exit_code == 0, result.stdout


def test_macro_record_and_replay():
    rec = runner.invoke(app, ["macro", "record", "a", "x j x j"])
    assert rec.exit_code == 0
    rep = runner.invoke(app, ["macro", "replay", "a"])
    assert rep.exit_code == 0
    assert "x j x j" in rep.stdout


def test_mix_set_gain():
    result = runner.invoke(app, ["mix", "set", "0", "gain", "-3"])
    assert result.exit_code == 0
    assert "gain" in result.stdout


def test_push2_map():
    result = runner.invoke(app, ["push2", "map"])
    assert result.exit_code == 0
    assert result.stdout.strip()

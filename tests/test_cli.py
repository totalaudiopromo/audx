"""CLI smoke tests via typer's CliRunner.

These exercise the offline command surface end to end without an audio device,
which also guards the lazy-PortAudio contract: importing/using the CLI must not
require the real-time backend.
"""

from pathlib import Path

import numpy as np
import soundfile as sf
from typer.testing import CliRunner

import pytest

from audx.cli import app
from audx.pattern import get_pattern_engine

runner = CliRunner()


@pytest.fixture(autouse=True)
def _reset_engine_state():
    """The pattern engine is a process-global singleton; CliRunner shares the
    process across tests, so clear it between tests to keep them isolated."""
    get_pattern_engine().patterns.clear()
    yield
    get_pattern_engine().patterns.clear()


def test_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "audx" in result.stdout


def test_synths_lists_voices():
    result = runner.invoke(app, ["synths"])
    assert result.exit_code == 0
    assert "kick" in result.stdout
    assert "cowbell" in result.stdout


def test_demo_renders_wav(tmp_path: Path):
    out = tmp_path / "demo.wav"
    result = runner.invoke(app, ["demo", str(out), "--bars", "1"])
    assert result.exit_code == 0, result.stdout
    assert out.exists()
    data, sr = sf.read(out, always_2d=True)
    assert sr == 44100
    assert float(np.max(np.abs(data))) > 0.0


def test_render_without_sample_uses_synth(tmp_path: Path):
    out = tmp_path / "r.wav"
    result = runner.invoke(app, ["render", "snare 2/8", "-o", str(out), "--bars", "1"])
    assert result.exit_code == 0, result.stdout
    assert out.exists()
    data, _ = sf.read(out, always_2d=True)
    assert float(np.max(np.abs(data))) > 0.0


def test_render_variations(tmp_path: Path):
    out = tmp_path / "v.wav"
    result = runner.invoke(
        app, ["render", "hh 16x8", "-o", str(out), "--variations", "3", "--bars", "1"]
    )
    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "v_v01.wav").exists()
    assert (tmp_path / "v_v03.wav").exists()


def test_pattern_create_reports_steps():
    result = runner.invoke(app, ["pattern", "create", "k", "kick 4/4"])
    assert result.exit_code == 0
    assert "4 steps" in result.stdout or "steps" in result.stdout


def test_doctor_runs():
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "audx doctor" in result.stdout


def test_init_scaffolds_project(tmp_path: Path):
    result = runner.invoke(app, ["init", "myloop", "--parent", str(tmp_path), "--no-git"])
    assert result.exit_code == 0, result.stdout
    assert (tmp_path / "myloop" / "project.audx").exists()
    assert (tmp_path / "myloop" / "stems").is_dir()
    assert (tmp_path / "myloop" / "renders").is_dir()


def test_export_midi_requires_patterns(tmp_path: Path):
    # fresh process has no in-process patterns -> friendly error, not a crash
    result = runner.invoke(app, ["export", "midi", str(tmp_path / "x.mid")])
    assert result.exit_code == 1
    assert not (tmp_path / "x.mid").exists()


def test_slot_roundtrip(tmp_path: Path):
    runner.invoke(app, ["init", "p", "--parent", str(tmp_path), "--no-git"])
    proj = tmp_path / "p" / "project.audx"
    assert proj.exists()
    set_result = runner.invoke(app, ["slot", "set", str(proj), "A"])
    assert set_result.exit_code == 0
    list_result = runner.invoke(app, ["slot", "list", str(proj)])
    assert list_result.exit_code == 0
    assert "A" in list_result.stdout


def test_diff_reports(tmp_path: Path):
    a = tmp_path / "a.audx"
    b = tmp_path / "b.audx"
    from audx.project import Project

    Project(name="a", bpm=120, patterns=[]).save(a)
    Project(name="a", bpm=140, patterns=[]).save(b)
    result = runner.invoke(app, ["diff", str(a), str(b)])
    assert result.exit_code == 0
    assert "120" in result.stdout or "140" in result.stdout


def test_render_with_real_sample(tmp_path: Path):
    sample = tmp_path / "clap.wav"
    sf.write(sample, np.ones((80, 1), dtype=np.float32) * 0.3, 44100)
    out = tmp_path / "real.wav"
    result = runner.invoke(
        app, ["render", "clap 4/4", "--sample", str(sample), "-o", str(out), "--bars", "1"]
    )
    assert result.exit_code == 0, result.stdout
    assert out.exists()

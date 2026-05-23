"""CLI commands called out by the design handoff spec."""

from pathlib import Path

import numpy as np
import soundfile as sf
from typer.testing import CliRunner

from audx.cli import app
from audx.pattern import get_pattern_engine
from audx.project import Project, init_project

runner = CliRunner()


def test_pattern_set_replaces_channel_dsl():
    engine = get_pattern_engine()
    engine.patterns.clear()

    result = runner.invoke(app, ["pattern", "set", "2", "snare 2/8"])

    assert result.exit_code == 0
    assert "ch 2" in result.output
    pattern = engine.patterns["ch2"]
    assert pattern.dsl == "snare 2/8 | channel 2"
    assert all(step.channel == 2 for step in pattern.steps)


def test_pattern_step_toggles_single_step():
    engine = get_pattern_engine()
    engine.patterns.clear()
    runner.invoke(app, ["pattern", "set", "1", "kick [0000]"])

    result = runner.invoke(app, ["pattern", "step", "1", "3", "on"])

    assert result.exit_code == 0
    pattern = engine.patterns["ch1"]
    assert pattern.dsl == "kick [0010] | channel 1"
    assert [step.beat for step in pattern.steps] == [2.0]


def test_load_audio_file_into_project_channel(tmp_path: Path):
    project_path = init_project("loadable", parent=tmp_path, git=False)
    sample_path = tmp_path / "snare.wav"
    sf.write(sample_path, np.ones((128, 1), dtype=np.float32) * 0.2, 44100)

    result = runner.invoke(app, ["load", str(sample_path), "--ch", "4", "--project", str(project_path)])

    assert result.exit_code == 0
    assert "loaded" in result.output
    project = Project.load(project_path)
    assert project.mixer[0]["channel"] == 4
    assert project.mixer[0]["sample"] == "stems/snare.wav"


def test_render_project_command_writes_wav(tmp_path: Path):
    project_path = init_project("render-cli", parent=tmp_path, git=False)
    sample_path = tmp_path / "kick.wav"
    sf.write(sample_path, np.ones((128, 1), dtype=np.float32) * 0.2, 44100)
    project = Project.load(project_path)
    project.add_stem(project_path, sample_path, channel=0, name="kick")
    project.save(project_path)
    output = tmp_path / "out.wav"

    result = runner.invoke(app, ["render-project", str(project_path), "--output", str(output), "--bars", "1"])

    assert result.exit_code == 0
    assert output.exists()

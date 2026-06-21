"""CLI tests for the multi-section `audx song` commands."""

import json
from pathlib import Path

import numpy as np
import soundfile as sf
from typer.testing import CliRunner

from audx.cli import app

runner = CliRunner()

SPEC = {
    "bpm": 120,
    "sections": {
        "intro": {"patterns": ["hh 16x8"], "bars": 2},
        "drop": {"patterns": ["kick 4/4", "bass e(5,16) | tune -7st"], "bars": 4},
    },
    "sequence": ["intro", "drop", "drop"],
}


def _write_spec(tmp_path: Path) -> Path:
    p = tmp_path / "song.json"
    p.write_text(json.dumps(SPEC))
    return p


def test_song_info(tmp_path: Path):
    result = runner.invoke(app, ["song", "info", str(_write_spec(tmp_path))])
    assert result.exit_code == 0, result.stdout
    assert "10 bars" in result.stdout  # 2 + 4 + 4
    assert "intro" in result.stdout and "drop" in result.stdout


def test_song_render(tmp_path: Path):
    out = tmp_path / "song.wav"
    result = runner.invoke(app, ["song", "render", str(_write_spec(tmp_path)), "-o", str(out)])
    assert result.exit_code == 0, result.stdout
    assert out.exists()
    data, sr = sf.read(out, always_2d=True)
    # 10 bars * 4 beats / 120bpm * 0.5 s/beat = 20 s
    assert abs(len(data) / sr - 20.0) < 0.5
    assert float(np.max(np.abs(data))) > 0.0


def test_song_missing_spec(tmp_path: Path):
    result = runner.invoke(app, ["song", "render", str(tmp_path / "nope.json")])
    assert result.exit_code == 1


def test_song_undefined_section_errors(tmp_path: Path):
    bad = dict(SPEC, sequence=["intro", "ghost"])
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad))
    result = runner.invoke(app, ["song", "info", str(p)])
    assert result.exit_code == 1

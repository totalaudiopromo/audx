"""Tests for offline arrangement rendering."""

from pathlib import Path

import numpy as np
import soundfile as sf

from audx.arrangement import Arrangement, render_arrangement, render_project
from audx.pattern import Pattern
from audx.project import Project, init_project
from audx.sampler import SampleLibrary


def test_render_arrangement_writes_wav(tmp_path: Path):
    sample_path = tmp_path / "kick.wav"
    sf.write(sample_path, np.ones((100, 1), dtype=np.float32) * 0.25, 44100)

    library = SampleLibrary(tmp_path)
    library.build_index(recursive=False)
    pattern = Pattern(name="kick", dsl="kick 4/4")
    pattern.parse_dsl()
    arrangement = Arrangement(bpm=120)
    arrangement.add(pattern, bars=1)

    out = render_arrangement(arrangement, library, tmp_path / "out.wav")
    assert out.exists()
    data, sr = sf.read(out, always_2d=True)
    assert sr == 44100
    assert data.shape[1] == 2
    assert float(np.max(np.abs(data))) > 0


def test_render_project_writes_mix_from_project_stem(tmp_path: Path):
    project_path = init_project("renderable", parent=tmp_path, git=False)
    sample_path = tmp_path / "kick.wav"
    sf.write(sample_path, np.ones((100, 1), dtype=np.float32) * 0.25, 44100)
    project = Project.load(project_path)
    project.add_stem(project_path, sample_path, channel=0, name="kick")
    project.save(project_path)

    out = render_project(project_path, tmp_path / "renderable.wav", bars=1)

    assert out.exists()
    data, sr = sf.read(out, always_2d=True)
    assert sr == 44100
    assert data.shape[1] == 2
    assert float(np.max(np.abs(data))) > 0

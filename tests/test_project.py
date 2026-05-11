"""Tests for project scaffolding, save/load, and diff."""

from __future__ import annotations

from pathlib import Path

import pytest

from audx.project import Project, diff_projects, init_project


def test_init_project_creates_folder_layout(tmp_path: Path) -> None:
    project_path = init_project("demo", parent=tmp_path, git=False)
    assert project_path == tmp_path / "demo" / "project.audx"
    assert project_path.exists()
    assert (tmp_path / "demo" / "stems").is_dir()
    assert (tmp_path / "demo" / "renders").is_dir()


def test_init_project_refuses_existing_non_empty(tmp_path: Path) -> None:
    (tmp_path / "demo").mkdir()
    (tmp_path / "demo" / "x.txt").write_text("hi", encoding="utf-8")
    with pytest.raises(FileExistsError):
        init_project("demo", parent=tmp_path, git=False)


def test_project_round_trip_preserves_finisher_and_slots(tmp_path: Path) -> None:
    path = init_project("rt", parent=tmp_path, git=False)
    loaded = Project.load(path)
    loaded.finisher["profile"] = "ukg"
    loaded.slots = {"A": [{"name": "kick", "dsl": "kick 4/4"}]}
    loaded.active_slot = "B"
    loaded.save(path)

    again = Project.load(path)
    assert again.finisher["profile"] == "ukg"
    assert again.slots == {"A": [{"name": "kick", "dsl": "kick 4/4"}]}
    assert again.active_slot == "B"


def test_diff_projects_reports_pattern_and_bpm_changes(tmp_path: Path) -> None:
    a = tmp_path / "a.audx"
    b = tmp_path / "b.audx"
    Project(
        name="a",
        bpm=120.0,
        patterns=[
            {"name": "kick", "dsl": "kick 4/4"},
            {"name": "snare", "dsl": "snare 2/8"},
        ],
        mixer=[{"channel": 0, "gain_db": 0.0, "mute": False}],
    ).save(a)
    Project(
        name="b",
        bpm=128.0,
        patterns=[
            {"name": "kick", "dsl": "kick 4/4 | swing 12%"},
            {"name": "hh", "dsl": "hh 16x8"},
        ],
        mixer=[{"channel": 0, "gain_db": -3.0, "mute": False}],
    ).save(b)

    lines = diff_projects(a, b)
    blob = "\n".join(lines)
    assert "bpm" in blob
    assert "120.0 → 128.0" in blob
    assert "+ hh" in blob
    assert "- snare" in blob
    assert "~ kick" in blob
    assert "ch0/gain" in blob

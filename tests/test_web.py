"""Tests for the read-only `audx serve` dashboard state."""

import pytest

from audx import web
from audx.pattern import Pattern, get_pattern_engine


@pytest.fixture(autouse=True)
def _clean_engine():
    get_pattern_engine().patterns.clear()
    yield
    get_pattern_engine().patterns.clear()


def _add(name: str, dsl: str, channel: int = 0) -> None:
    p = Pattern(name=name, dsl=dsl, channel=channel)
    p.parse_dsl()
    get_pattern_engine().add_pattern(p)


def test_step_grid_four_on_floor():
    p = Pattern(name="k", dsl="kick 4/4")
    p.parse_dsl()
    assert web._step_grid(p) == [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]


def test_state_shape_and_tracks():
    _add("kick", "kick 4/4", channel=0)
    _add("hats", "hh 16x8", channel=2)
    s = web._state()
    assert {"bpm", "bar", "beat", "step", "playing", "levels", "tracks"} <= set(s)
    names = {t["name"]: t for t in s["tracks"]}
    assert names["kick"]["channel"] == 0
    assert sum(names["kick"]["steps"]) == 4
    assert len(names["hats"]["steps"]) == 16


def test_state_empty_when_no_patterns():
    s = web._state()
    assert s["tracks"] == []


def test_dashboard_is_html():
    assert web.DASHBOARD.lstrip().startswith("<!doctype html>")
    assert "/state" in web.DASHBOARD

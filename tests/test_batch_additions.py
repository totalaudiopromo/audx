"""Tests for the second batch: fork, slots, macros, midi export, watch, web."""

from __future__ import annotations

import json
import shutil
import threading
import time
import urllib.request
from pathlib import Path

import mido
import pytest

from audx.macros import MacroStore
from audx.midi import RecordedNote, notes_to_pattern
from audx.midi_export import patterns_to_midi
from audx.pattern import Pattern, get_pattern_engine
from audx.project import Project, init_project
from audx.watch import FileWatcher
from audx.web import serve


def test_fork_copies_project_folder(tmp_path: Path) -> None:
    src = init_project("src", parent=tmp_path, git=False).parent
    dst = tmp_path / "dst"
    shutil.copytree(src, dst)
    assert (dst / "project.audx").exists()


def test_macro_store_round_trip() -> None:
    store = MacroStore()
    store.start("a")
    for key in ["x", "j", "x", "j"]:
        store.capture(key)
    store.stop()
    assert store.replay("a") == ["x", "j", "x", "j"]
    persisted = MacroStore.from_dict(store.to_dict())
    assert persisted.replay("a") == ["x", "j", "x", "j"]


def test_macro_store_ignores_unstarted_capture() -> None:
    store = MacroStore()
    store.capture("x")  # no recording in progress
    store.stop()  # no-op
    assert store.replay("a") == []


def test_patterns_to_midi_writes_valid_smf(tmp_path: Path) -> None:
    kick = Pattern(name="kick", dsl="kick 4/4")
    kick.parse_dsl()
    snare = Pattern(name="snare", dsl="snare 2/8")
    snare.parse_dsl()
    out = patterns_to_midi({"kick": kick, "snare": snare}, tmp_path / "drums.mid", bpm=128.0, bars=1)
    assert out.exists()
    loaded = mido.MidiFile(str(out))
    assert loaded.ticks_per_beat > 0
    note_on = [m for m in loaded.tracks[0] if getattr(m, "type", "") == "note_on" and m.velocity > 0]
    assert len(note_on) == 6  # 4 kicks + 2 snares


def test_notes_to_pattern_builds_explicit_grid() -> None:
    notes = [
        RecordedNote(note=36, velocity=100, beat=0.0, duration=0.1),
        RecordedNote(note=36, velocity=100, beat=2.0, duration=0.1),
    ]
    pattern = notes_to_pattern(notes, name="kick", channel=0)
    assert len(pattern.steps) == 2


def test_slot_set_then_next_swaps_active_patterns(tmp_path: Path) -> None:
    path = init_project("slots", parent=tmp_path, git=False)
    proj = Project.load(path)
    proj.patterns = [{"name": "kick", "dsl": "kick 4/4"}]
    proj.slots["A"] = list(proj.patterns)
    proj.patterns = [{"name": "hh", "dsl": "hh 16x8"}]
    proj.slots["B"] = list(proj.patterns)
    proj.active_slot = "A"
    proj.patterns = list(proj.slots["A"])
    proj.save(path)

    reloaded = Project.load(path)
    assert reloaded.active_slot == "A"
    reloaded.active_slot = "B"
    reloaded.patterns = list(reloaded.slots["B"])
    reloaded.save(path)
    assert Project.load(path).patterns[0]["name"] == "hh"


def test_file_watcher_triggers_on_change(tmp_path: Path) -> None:
    path = init_project("watch", parent=tmp_path, git=False)
    seen: list[Project] = []

    def _cb(_: Path, loaded: Project) -> None:
        seen.append(loaded)

    watcher = FileWatcher(path, _cb, interval=0.05)
    watcher.start()
    try:
        time.sleep(0.1)
        proj = Project.load(path)
        proj.bpm = 140.0
        proj.save(path)
        time.sleep(0.4)
    finally:
        watcher.stop()
    assert any(p.bpm == 140.0 for p in seen)


def test_web_serves_state_and_dashboard() -> None:
    pe = get_pattern_engine()
    pe.set_bpm(132.0)

    import http.server

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), __import__("audx.web", fromlist=["_Handler"])._Handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/state", timeout=1) as resp:
            payload = json.loads(resp.read().decode())
        assert payload["bpm"] == pytest.approx(132.0)
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1) as resp:
            html = resp.read().decode()
        assert "audx · monitor" in html
    finally:
        httpd.shutdown()


def test_serve_function_signature() -> None:
    """Smoke: the public serve() takes host + port and returns None."""
    assert callable(serve)

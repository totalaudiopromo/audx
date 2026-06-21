"""Guard: the committed web golden-vector fixtures match the live parser.

If src/audx/pattern.py changes the parse output, these fail until someone reruns
``python scripts/gen_web_fixtures.py`` — keeping the TS port's contract honest.
"""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEN = ROOT / "scripts" / "gen_web_fixtures.py"
FIXTURES = ROOT / "web" / "fixtures"


def _load_generator():
    spec = importlib.util.spec_from_file_location("gen_web_fixtures", GEN)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_dsl_fixtures_current():
    gen = _load_generator()
    committed = json.loads((FIXTURES / "dsl.json").read_text())
    assert committed == gen.build_dsl_fixtures(), (
        "web/fixtures/dsl.json is stale — run scripts/gen_web_fixtures.py"
    )


def test_swing_fixtures_current():
    gen = _load_generator()
    committed = json.loads((FIXTURES / "swing.json").read_text())
    assert committed == gen.build_swing_fixtures(), (
        "web/fixtures/swing.json is stale — run scripts/gen_web_fixtures.py"
    )


def test_synth_fixtures_current():
    gen = _load_generator()
    committed = json.loads((FIXTURES / "synth.json").read_text())
    assert committed == gen.build_synth_fixtures(), (
        "web/fixtures/synth.json is stale — run scripts/gen_web_fixtures.py"
    )


def test_push2_fixtures_current():
    gen = _load_generator()
    committed = json.loads((FIXTURES / "push2.json").read_text())
    assert committed == gen.build_push2_fixtures(), (
        "web/fixtures/push2.json is stale — run scripts/gen_web_fixtures.py"
    )


def test_song_fixtures_current():
    gen = _load_generator()
    committed = json.loads((FIXTURES / "song.json").read_text())
    assert committed == gen.build_song_fixtures(), (
        "web/fixtures/song.json is stale — run scripts/gen_web_fixtures.py"
    )

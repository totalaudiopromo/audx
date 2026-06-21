"""Tests for the browser playground render path (site/audx_web/webrender.py).

Imports webrender directly; via its dual-import it uses the real ``audx`` package
here, so this exercises the same DSL parser + synth the CLI uses.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

WEB_DIR = Path(__file__).resolve().parent.parent / "site" / "audx_web"
sys.path.insert(0, str(WEB_DIR))

import webrender  # noqa: E402


def test_render_makes_stereo_sound():
    mix = webrender.render_mix(["kick 4/4", "hh 16x8"], bpm=120, bars=1, sr=48000)
    assert mix.dtype == np.float32
    assert mix.ndim == 2 and mix.shape[1] == 2
    # 1 bar * 4 beats / 120bpm * 0.5 s/beat = 2 s at 48k
    assert abs(mix.shape[0] - 96000) < 600
    assert float(np.max(np.abs(mix))) > 0.0


def test_unknown_and_blank_lines_are_skipped():
    mix = webrender.render_mix(["", "# a comment", "wobble 4/4"], bars=1)
    assert float(np.max(np.abs(mix))) == 0.0  # nothing audible, no crash


def test_melodic_and_modifiers_render():
    mix = webrender.render_mix(["bass e(5,16) | tune -7st | vel 0.8"], bars=1)
    assert float(np.max(np.abs(mix))) > 0.0


def test_no_clipping_past_full_scale():
    mix = webrender.render_mix(["kick 4/4"] * 6, bars=1)  # stacked, would clip
    assert float(np.max(np.abs(mix))) <= 1.0 + 1e-6


@pytest.mark.parametrize("module", ["synth.py", "pattern.py"])
def test_bundled_modules_match_source(module):
    """The browser copies must equal src/ (run scripts/sync-web-modules.sh)."""
    src = Path(__file__).resolve().parent.parent / "src" / "audx" / module
    bundled = WEB_DIR / module
    assert bundled.read_bytes() == src.read_bytes(), (
        f"{module} drifted — run scripts/sync-web-modules.sh"
    )

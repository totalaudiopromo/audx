"""Main Textual TUI application."""

from __future__ import annotations

import time
from pathlib import Path
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Footer, Header, Label, Static

from audx.config import AUDX_BPM, CHANNELS_COUNT, CONFIG_DIR, DEFAULT_BPM
from audx.engine import get_engine, init_engine
from audx.pattern import get_pattern_engine
from audx.project import Project

# ── Live finger-drumming pads ─────────────────────────────────────────────────
#
# Map a keyboard key → (synth voice name, mixer channel). While the TUI is open
# the user can play these built-in synth voices live, like a drum-pad MPC row.
#
# The digit keys 1-9 are already bound (channel mute toggles) and `q`/`t`/`m`
# are bound to quit/tap/mute, so the pads deliberately use a fresh QWERTY-style
# pad block that avoids every existing binding:
#
#     w  e  r        kick  snare  clap        (ch 0  1  2)
#     a  s  d  f     hh    oh     rim   tom    (ch 3  4  5  6)
#     z  x  c        cowbell perc  sub          (ch 7  8  9)
#     u  i  o        ride   crash  shaker       (ch 10 11 12)
#
# Each value is (voice_name, channel). Keep this a plain module-level dict so it
# can be unit-tested without instantiating the Textual app.
SYNTH_PADS: dict[str, tuple[str, int]] = {
    "w": ("kick", 0),
    "e": ("snare", 1),
    "r": ("clap", 2),
    "a": ("hh", 3),
    "s": ("oh", 4),
    "d": ("rim", 5),
    "f": ("tom", 6),
    "z": ("cowbell", 7),
    "x": ("perc", 8),
    "c": ("sub", 9),
    "u": ("ride", 10),
    "i": ("crash", 11),
    "o": ("shaker", 12),
}


def pad_for_key(key: str) -> tuple[str, int] | None:
    """Return the ``(voice, channel)`` pad for ``key``, or ``None`` if unmapped."""
    return SYNTH_PADS.get(key)


class VUMeter(Static):
    """Small text VU meter."""

    level: reactive[float] = reactive(0.0)

    def render(self) -> str:
        level = max(0.0, min(float(self.level), 1.0))
        width = 10
        filled = int(level * width)
        return "█" * filled + "░" * (width - filled)


class ChannelStrip(Vertical):
    """A compact mixer channel strip."""

    def __init__(self, channel: int, label: str = "", **kwargs):
        super().__init__(**kwargs)
        self.channel = channel
        self.label = label or f"Ch {channel + 1}"
        self.gain = 1.0

    def compose(self) -> ComposeResult:
        yield Label(self.label, id=f"label-{self.channel}")
        yield VUMeter(id=f"vu-{self.channel}")
        yield Static("gain 1.00", id=f"gain-{self.channel}")
        yield Button("-", id=f"gain-down-{self.channel}", variant="default")
        yield Button("+", id=f"gain-up-{self.channel}", variant="default")
        yield Button("Mute", id=f"mute-{self.channel}", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        engine = get_engine()
        if engine is None:
            return
        button_id = event.button.id or ""
        if button_id == f"mute-{self.channel}":
            engine.channel_mute[self.channel] = not bool(engine.channel_mute[self.channel])
            event.button.variant = "success" if engine.channel_mute[self.channel] else "default"
            return
        if button_id == f"gain-down-{self.channel}":
            self._set_gain(self.gain - 0.05)
        elif button_id == f"gain-up-{self.channel}":
            self._set_gain(self.gain + 0.05)

    def _set_gain(self, value: float) -> None:
        self.gain = max(0.0, min(value, 2.0))
        engine = get_engine()
        if engine is not None:
            engine.channel_gain[self.channel] = self.gain
        self.query_one(f"#gain-{self.channel}", Static).update(f"gain {self.gain:.2f}")


class PatternRow(Horizontal):
    """Pattern controls.

    This is deliberately conservative: it toggles enabled state without deleting
    the pattern object. The previous version deleted patterns, so a mis-click
    lost work.
    """

    def compose(self) -> ComposeResult:
        pattern_engine = get_pattern_engine()
        if not pattern_engine.patterns:
            yield Static("patterns: none", id="patterns-empty")
            return
        for name, pattern in pattern_engine.patterns.items():
            active = pattern.metadata.get("enabled", True) if hasattr(pattern, "metadata") else True
            yield Button(name, id=f"pat-{name}", variant="success" if active else "default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        name = (event.button.id or "").replace("pat-", "", 1)
        pattern = get_pattern_engine().patterns.get(name)
        if pattern is None:
            return
        if not hasattr(pattern, "metadata"):
            pattern.metadata = {}
        enabled = not pattern.metadata.get("enabled", True)
        pattern.metadata["enabled"] = enabled
        event.button.variant = "success" if enabled else "default"


class TapTempoCounter:
    """Compute BPM from recent taps."""

    def __init__(self, max_taps: int = 8):
        self.max_taps = max_taps
        self.times: list[float] = []

    def tap(self, now: float | None = None) -> float | None:
        now = time.time() if now is None else now
        self.times = [tap_time for tap_time in self.times if now - tap_time <= 5.0]
        self.times.append(now)
        self.times = self.times[-self.max_taps :]
        if len(self.times) < 2:
            return None
        intervals = [b - a for a, b in zip(self.times, self.times[1:], strict=False) if b > a]
        if not intervals:
            return None
        return round(60.0 / (sum(intervals) / len(intervals)), 1)


class TransportBar(Horizontal):
    """Transport controls."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.playing = False

    def compose(self) -> ComposeResult:
        yield Button("▶", id="play", variant="success")
        yield Button("■", id="stop", variant="error")
        yield Static(f"BPM {DEFAULT_BPM}", id="bpm")
        yield Button("tap", id="tap", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        engine = get_engine() or init_engine()
        pattern_engine = get_pattern_engine()
        button_id = event.button.id
        if button_id == "play":
            engine.start()
            pattern_engine.start()
            self.playing = True
            event.button.label = "Ⅱ"
            event.button.variant = "warning"
        elif button_id == "stop":
            engine.stop()
            pattern_engine.stop()
            self.playing = False
            self.query_one("#play", Button).label = "▶"
            self.query_one("#play", Button).variant = "success"
        elif button_id == "tap":
            bpm = self.app.tap_counter.tap()
            if bpm is not None:
                self.app.set_bpm(bpm)
                self.query_one("#bpm", Static).update(f"BPM {bpm}")


class StatusLine(Static):
    """Bottom status: mode indicator + active pattern slot."""

    def render(self) -> str:
        app = self.app
        slot = getattr(app, "active_slot", "A")
        mode = getattr(app, "mode", "NORMAL")
        slots = " · ".join(
            f"[{s}]" if s == slot else s for s in ("A", "B", "C", "D")
        )
        return f"[{mode}]  PAT {slots}  ·  ? help  ·  q quit"


class PadHint(Static):
    """Subtle one-line hint listing the live drum-pad keys."""

    def render(self) -> str:
        order = ("w", "e", "r", "a", "s", "d", "f", "z", "x", "c", "u", "i", "o")
        pads = " ".join(f"{k}:{SYNTH_PADS[k][0]}" for k in order if k in SYNTH_PADS)
        return f"pads  {pads}"


class DAWApp(App):
    """audx TUI: compact mixer + transport with vim-style modal bindings."""

    CSS = """
    Screen { background: #111111; color: #e0e0e0; }
    Header { background: #1e1e1e; color: #d4a574; text-style: bold; }
    Footer { background: #1e1e1e; }
    #mixer { height: 1fr; }
    ChannelStrip { width: 9; background: #1e1e1e; border: solid #333333; margin: 1; }
    VUMeter { color: #a8c087; height: 1; }
    PatternRow { height: 3; background: #161616; border: solid #333333; margin: 1; }
    TransportBar { height: 3; background: #1e1e1e; border: solid #333333; margin: 1; }
    StatusLine { height: 1; background: #1e1e1e; color: #d4a574; }
    PadHint { height: 1; background: #161616; color: #7a8a6a; text-style: dim; }
    """

    TITLE = "audx"
    SUB_TITLE = "code your music"

    SLOT_KEYS: ClassVar[dict[str, str]] = {
        "A": "shift+1",
        "B": "shift+2",
        "C": "shift+3",
        "D": "shift+4",
    }

    def __init__(self, project: Path | None = None, samples_dir: Path | None = None):
        super().__init__()
        self.project = project
        self.samples_dir = samples_dir
        self.tap_counter = TapTempoCounter()
        self.active_slot = "A"
        self.mode = "NORMAL"
        self.selected_channel = 0

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="mixer"):
            for channel in range(CHANNELS_COUNT):
                yield ChannelStrip(channel=channel, label=f"{channel + 1:02d}")
        yield PatternRow()
        yield TransportBar()
        yield PadHint(id="pad-hint")
        yield StatusLine(id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(0.05, self.update_meters)
        engine = init_engine()
        bpm = float(AUDX_BPM)
        engine.set_bpm(bpm)
        get_pattern_engine().set_bpm(bpm)

    def on_unmount(self) -> None:
        self.auto_save_last_project()

    def auto_save_last_project(self) -> Path:
        pattern_engine = get_pattern_engine()
        patterns = [
            {
                "name": name,
                "dsl": pattern.dsl,
                "length_beats": pattern.length_beats,
                "channel": pattern.channel,
                "swing": pattern.swing,
            }
            for name, pattern in pattern_engine.patterns.items()
        ]
        path = CONFIG_DIR / "last.audx"
        project = Project(name="last", bpm=pattern_engine.bpm, patterns=patterns)
        project.save(path)
        return path

    def update_meters(self) -> None:
        engine = get_engine()
        if engine is None:
            return
        levels = engine.get_channel_levels()
        for channel in range(min(CHANNELS_COUNT, len(levels))):
            self.query_one(f"#vu-{channel}", VUMeter).level = float(levels[channel])

    def _trigger_pad(self, key: str) -> bool:
        """Play the live synth pad bound to ``key``. Returns True if consumed."""
        pad = pad_for_key(key)
        if pad is None:
            return False
        voice, channel = pad
        engine = get_engine() or init_engine()
        if engine is not None:
            engine.play_synth(voice, channel)
        return True

    def on_key(self, event) -> None:
        """Modal keymap per spec §04 (NORMAL mode keys)."""
        key = event.key
        engine = get_engine()
        pattern_engine = get_pattern_engine()

        # Live finger-drumming: pad keys play a synth voice and are otherwise
        # not consumed by any existing binding, so handle them first.
        if self._trigger_pad(key):
            return

        if key == "space":
            play_button = self.query_one("#play", Button)
            if str(play_button.label) == "▶":
                play_button.press()
            else:
                self.query_one("#stop", Button).press()
        elif key == "full_stop" or key == ".":
            # stop + return to bar 1
            if engine is not None:
                engine.stop()
            pattern_engine.stop()
            pattern_engine.current_bar = 0
            pattern_engine.current_beat = 0.0
        elif key in "123456789":
            channel = int(key) - 1
            if channel < CHANNELS_COUNT:
                self.selected_channel = channel
                self.query_one(f"#mute-{channel}", Button).press()
        elif key in {"left_square_bracket", "["}:
            self.set_bpm(max(20.0, pattern_engine.bpm - 1.0))
        elif key in {"right_square_bracket", "]"}:
            self.set_bpm(min(300.0, pattern_engine.bpm + 1.0))
        elif key in {"left_curly_bracket", "{"}:
            self._adjust_selected_swing(-0.01)
        elif key in {"right_curly_bracket", "}"}:
            self._adjust_selected_swing(0.01)
        elif key == "t":
            self.query_one("#tap", Button).press()
        elif key == "m":
            self.query_one(f"#mute-{self.selected_channel}", Button).press()
        elif key == "q":
            self.exit()
        elif key in {"shift+1", "shift+2", "shift+3", "shift+4"}:
            slot_index = int(key.split("+")[1])
            self.active_slot = "ABCD"[slot_index - 1]
            self.query_one("#status", StatusLine).refresh()

    def _adjust_selected_swing(self, delta: float) -> None:
        engine = get_pattern_engine()
        for pattern in engine.patterns.values():
            if pattern.channel == self.selected_channel:
                pattern.swing = max(0.0, min(pattern.swing + delta, 1.0))

    def set_bpm(self, bpm: float) -> None:
        engine = get_engine()
        if engine is not None:
            engine.set_bpm(bpm)
        get_pattern_engine().set_bpm(bpm)


def run_tui(project: Path | None = None, samples_dir: Path | None = None) -> None:
    DAWApp(project=project, samples_dir=samples_dir).run()


__all__ = ["SYNTH_PADS", "DAWApp", "TapTempoCounter", "pad_for_key", "run_tui"]

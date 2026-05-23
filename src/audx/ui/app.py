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


def _db(level: float) -> str:
    if level <= 0.00001:
        return "-inf"
    import math

    return f"{20 * math.log10(level):+5.1f}"


def _level_bar(level: float, width: int = 24) -> str:
    level = max(0.0, min(float(level), 1.0))
    filled = int(level * width)
    return "█" * filled + "░" * (width - filled)


def _pattern_grid(pattern, cells: int = 16) -> list[bool]:
    grid = [False] * cells
    for step in pattern.steps:
        index = round((step.beat % pattern.length_beats) / pattern.length_beats * cells)
        if 0 <= index < cells:
            grid[index] = True
    return grid


class TransportHeader(Static):
    """Fixed-width transport header inspired by the CLI spec."""

    def render(self) -> str:
        pattern_engine = get_pattern_engine()
        engine = get_engine()
        playing = bool(pattern_engine.running)
        project = Path(getattr(self.app, "project", "") or "last.audx").name
        bpm = f"{pattern_engine.bpm:06.1f}"
        pos = f"{pattern_engine.current_bar + 1:03d}:{int(pattern_engine.current_beat) + 1:02d}"
        rate = getattr(engine, "sample_rate", 48000) if engine else 48000
        title = f"{'▶' if playing else '■'} audx  {project}"
        right = f"{'▶' if playing else '■'} {bpm} bpm  4/4  {rate // 1000:02d}k  cpu --  bar {pos}"
        width = max(80, self.app.size.width if self.app.size else 100)
        gap = max(1, width - len(title) - len(right) - 1)
        return f"{title}{' ' * gap}{right}"


class MixerTable(Static):
    """Dense row-based mixer table."""

    def render(self) -> str:
        engine = get_engine()
        pattern_engine = get_pattern_engine()
        levels = engine.get_channel_levels() if engine else [0.0] * CHANNELS_COUNT
        patterns = list(pattern_engine.patterns.values())
        by_channel = {pattern.channel: pattern for pattern in patterns}
        selected = getattr(self.app, "selected_channel", 0)
        rows = ["ch  · name      lvl                            peak    gain    M S    sample / dsl"]
        for channel in range(CHANNELS_COUNT):
            pattern = by_channel.get(channel)
            level = float(levels[channel]) if channel < len(levels) else 0.0
            gain = float(engine.channel_gain[channel]) if engine is not None else 1.0
            muted = bool(engine.channel_mute[channel]) if engine is not None else False
            marker = "▮" if pattern and not muted else "·"
            name = (pattern.name if pattern else f"ch{channel:02d}")[:8]
            detail = pattern.dsl if pattern else "— empty —"
            cursor = ">" if channel == selected else " "
            mute = "M" if muted else " "
            rows.append(
                f"{cursor}{channel + 1:02d}  {marker} {name:<8} "
                f"{_level_bar(level)}  {_db(level):>7}  {_db(gain):>6}   {mute}      {detail[:42]}"
            )
        return "\n".join(rows)


class PatternGrid(Static):
    """Step grid for the currently loaded patterns."""

    def render(self) -> str:
        pattern_engine = get_pattern_engine()
        patterns = list(pattern_engine.patterns.values())
        selected_channel = getattr(self.app, "selected_channel", 0)
        selected_step = getattr(self.app, "selected_step", 0)
        playhead = int((pattern_engine.current_beat / 4.0) * 16) % 16
        rows = ["     " + "  ".join(f"{i:02d}" for i in range(1, 17))]
        if not patterns:
            rows.append("     · no patterns yet · `audx pattern set 0 \"kick 4/4\"`")
            return "\n".join(rows)
        for pattern in patterns[:8]:
            grid = _pattern_grid(pattern)
            cells = []
            for index, active in enumerate(grid):
                if pattern.channel == selected_channel and index == selected_step:
                    cells.append("▣" if active else "□")
                elif index == playhead and pattern_engine.running:
                    cells.append("▓" if active else "▒")
                else:
                    cells.append("█" if active else "·")
            rows.append(f"{pattern.name[:4]:<4} " + "   ".join(cells))
        return "\n".join(rows)


class CommandLine(Static):
    """Bottom command prompt."""

    def render(self) -> str:
        mode = getattr(self.app, "mode", "NORMAL")
        command = getattr(self.app, "command_buffer", "")
        prefix = ":" if mode == "COMMAND" else "audx>"
        return f"{prefix} {command}"


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


class DAWApp(App):
    """audx TUI: compact mixer + transport with vim-style modal bindings."""

    CSS = """
    Screen { background: #111111; color: #e0e0e0; }
    Header { background: #1e1e1e; color: #d4a574; text-style: bold; }
    Footer { background: #1e1e1e; }
    #transport-header { height: 1; color: #d4a574; background: #08070a; }
    #divider-a, #divider-b, #divider-c { height: 1; color: #4a4238; }
    #mixer-table { height: auto; color: #e8dccb; }
    #pattern-grid { height: auto; color: #e8dccb; }
    #command-line { height: 1; color: #d4a574; background: #0e0c10; }
    #mixer { height: 1fr; }
    ChannelStrip { width: 9; background: #1e1e1e; border: solid #333333; margin: 1; }
    VUMeter { color: #a8c087; height: 1; }
    PatternRow { height: 3; background: #161616; border: solid #333333; margin: 1; }
    TransportBar { height: 3; background: #1e1e1e; border: solid #333333; margin: 1; }
    StatusLine { height: 1; background: #1e1e1e; color: #d4a574; }
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
        self.selected_step = 0
        self.command_buffer = ""

    def compose(self) -> ComposeResult:
        yield Header()
        yield TransportHeader(id="transport-header")
        yield Static("─" * 120, id="divider-a")
        yield MixerTable(id="mixer-table")
        yield Static("─" * 120, id="divider-b")
        yield PatternGrid(id="pattern-grid")
        yield Static("─" * 120, id="divider-c")
        yield CommandLine(id="command-line")
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
        for widget_id in ("#transport-header", "#mixer-table", "#pattern-grid", "#command-line", "#status"):
            self.query_one(widget_id, Static).refresh()

    def on_key(self, event) -> None:
        """Modal keymap per spec §04 (NORMAL mode keys)."""
        key = event.key
        engine = get_engine()
        pattern_engine = get_pattern_engine()

        if key == "space":
            engine = engine or init_engine()
            if pattern_engine.running:
                engine.stop()
                pattern_engine.stop()
            else:
                engine.start()
                pattern_engine.start()
        elif key == "full_stop" or key == ".":
            # stop + return to bar 1
            if engine is not None:
                engine.stop()
            pattern_engine.stop()
            pattern_engine.current_bar = 0
            pattern_engine.current_beat = 0.0
        elif key in {"h", "left"}:
            self.selected_step = max(0, self.selected_step - 1)
        elif key in {"l", "right"}:
            self.selected_step = min(15, self.selected_step + 1)
        elif key in {"j", "down"}:
            self.selected_channel = min(CHANNELS_COUNT - 1, self.selected_channel + 1)
        elif key in {"k", "up"}:
            self.selected_channel = max(0, self.selected_channel - 1)
        elif key == "x":
            self._toggle_selected_step()
        elif key in "123456789":
            channel = int(key) - 1
            if channel < CHANNELS_COUNT:
                self.selected_channel = channel
        elif key in {"left_square_bracket", "["}:
            self.set_bpm(max(20.0, pattern_engine.bpm - 1.0))
        elif key in {"right_square_bracket", "]"}:
            self.set_bpm(min(300.0, pattern_engine.bpm + 1.0))
        elif key in {"left_curly_bracket", "{"}:
            self._adjust_selected_swing(-0.01)
        elif key in {"right_curly_bracket", "}"}:
            self._adjust_selected_swing(0.01)
        elif key == "t":
            bpm = self.tap_counter.tap()
            if bpm is not None:
                self.set_bpm(bpm)
        elif key == "m":
            engine = engine or init_engine()
            engine.channel_mute[self.selected_channel] = not bool(engine.channel_mute[self.selected_channel])
        elif key == "colon" or key == ":":
            self.mode = "COMMAND"
            self.command_buffer = ""
        elif key == "escape":
            self.mode = "NORMAL"
            self.command_buffer = ""
        elif key == "q":
            self.exit()
        elif key in {"shift+1", "shift+2", "shift+3", "shift+4"}:
            slot_index = int(key.split("+")[1])
            self.active_slot = "ABCD"[slot_index - 1]
            self.query_one("#status", StatusLine).refresh()
        self.query_one("#mixer-table", MixerTable).refresh()
        self.query_one("#pattern-grid", PatternGrid).refresh()
        self.query_one("#transport-header", TransportHeader).refresh()
        self.query_one("#command-line", CommandLine).refresh()

    def _toggle_selected_step(self) -> None:
        pattern = self._selected_pattern()
        if pattern is None:
            pattern = ProjectPatternFactory.create_empty(self.selected_channel)
            get_pattern_engine().add_pattern(pattern)
        grid = _pattern_grid(pattern)
        grid[self.selected_step] = not grid[self.selected_step]
        source = pattern.steps[0].sample if pattern.steps else pattern.name
        pattern.dsl = f"{source} [{''.join('1' if cell else '0' for cell in grid)}] | channel {self.selected_channel}"
        pattern.parse_dsl()

    def _selected_pattern(self):
        for pattern in get_pattern_engine().patterns.values():
            if pattern.channel == self.selected_channel:
                return pattern
        return None

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


class ProjectPatternFactory:
    """Small factory kept out of key handling so empty-track creation is clear."""

    @staticmethod
    def create_empty(channel: int):
        from audx.pattern import Pattern

        pattern = Pattern(name=f"ch{channel}", dsl=f"ch{channel} [0000000000000000] | channel {channel}", channel=channel)
        pattern.parse_dsl()
        return pattern


def run_tui(project: Path | None = None, samples_dir: Path | None = None) -> None:
    DAWApp(project=project, samples_dir=samples_dir).run()


__all__ = ["DAWApp", "TapTempoCounter", "run_tui"]

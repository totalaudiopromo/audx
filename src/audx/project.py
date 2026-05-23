"""Project save/load, scaffolding, and diff."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from audx.config import PROJECTS_DIR
from audx.pattern import Pattern

PATTERN_SLOTS = ("A", "B", "C", "D")


@dataclass
class MixerChannel:
    """Per-channel mixer state persisted in the project file."""

    channel: int
    name: str = ""
    gain_db: float = 0.0
    pan: float = 0.0
    mute: bool = False
    solo: bool = False
    sample: str | None = None


@dataclass
class FinisherConfig:
    """Per-project mastering preferences. Maps 1:1 to finisher CLI flags."""

    profile: str = "house"
    platform: str = "spotify"
    loudness: str = "streaming"
    tone: str = "neutral"
    energy: str = "med"
    reference: str | None = None
    use_stems: bool = False
    drums_up: int = 0
    bass_down: int = 0


@dataclass
class Project:
    name: str
    bpm: float = 120.0
    time_sig: str = "4/4"
    patterns: list[dict[str, Any]] = field(default_factory=list)
    slots: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    active_slot: str = "A"
    mixer: list[dict[str, Any]] = field(default_factory=list)
    finisher: dict[str, Any] = field(default_factory=lambda: asdict(FinisherConfig()))
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        with path.open("w") as f:
            json.dump(data, f, indent=2, sort_keys=True)

    @classmethod
    def load(cls, path: Path) -> Project:
        with Path(path).open() as f:
            data = json.load(f)
        # Tolerate older projects that lack the new fields.
        return cls(
            name=data.get("name", Path(path).stem),
            bpm=data.get("bpm", 120.0),
            time_sig=data.get("time_sig", "4/4"),
            patterns=data.get("patterns", []),
            slots=data.get("slots", {}),
            active_slot=data.get("active_slot", "A"),
            mixer=data.get("mixer", []),
            finisher=data.get("finisher", asdict(FinisherConfig())),
            created_at=data.get("created_at", datetime.now().isoformat()),
        )

    def apply_to_engine(self) -> None:
        """Restore patterns into the in-process pattern engine."""
        from audx.engine import get_engine
        from audx.pattern import get_pattern_engine

        eng = get_pattern_engine()
        eng.set_bpm(self.bpm)
        eng.patterns.clear()
        for pdata in self.patterns:
            pat = Pattern(
                name=pdata["name"],
                dsl=pdata["dsl"],
                length_beats=pdata.get("length_beats", 4),
                channel=pdata.get("channel", 0),
                swing=pdata.get("swing", 0.0),
            )
            pat.parse_dsl()
            eng.add_pattern(pat)

        audio = get_engine()
        if audio is not None:
            for ch in self.mixer:
                idx = int(ch.get("channel", 0))
                if 0 <= idx < len(audio.channel_gain):
                    audio.channel_gain[idx] = _gain_to_linear(float(ch.get("gain_db", 0.0)))
                    audio.channel_mute[idx] = bool(ch.get("mute", False))

    def add_stem(
        self,
        project_path: Path,
        source: Path,
        channel: int,
        name: str | None = None,
        copy: bool = True,
    ) -> str:
        """Add an audio file to the project and create a playable channel pattern."""
        project_dir = Path(project_path).parent
        source = Path(source).expanduser()
        if not source.exists():
            raise FileNotFoundError(source)

        stem_name = source.name
        target = project_dir / "stems" / stem_name
        target.parent.mkdir(parents=True, exist_ok=True)
        if copy:
            if source.resolve() != target.resolve():
                shutil.copy2(source, target)
        else:
            target = source

        rel_path = target.relative_to(project_dir).as_posix() if target.is_relative_to(project_dir) else str(target)
        track_name = name or source.stem
        mixer_row = {
            "channel": channel,
            "name": track_name,
            "gain_db": 0.0,
            "pan": 0.0,
            "mute": False,
            "solo": False,
            "sample": rel_path,
        }
        self.mixer = [row for row in self.mixer if int(row.get("channel", -1)) != channel]
        self.mixer.append(mixer_row)
        pattern = {
            "name": track_name,
            "dsl": f'{track_name} "{rel_path}" [1] | channel {channel}',
            "length_beats": 4,
            "channel": channel,
        }
        self.patterns = [row for row in self.patterns if int(row.get("channel", -1)) != channel]
        self.patterns.append(pattern)
        return rel_path


def _gain_to_linear(db: float) -> float:
    return 10 ** (db / 20)


# Template presets
TEMPLATES = {
    "empty": Project(name="empty", bpm=120.0),
    "techno": Project(
        name="techno",
        bpm=135.0,
        patterns=[
            {"name": "kick", "dsl": "kick 4/4"},
            {"name": "hihat", "dsl": "hh 8x8"},
            {"name": "clap", "dsl": "clap 2/8"},
        ],
    ),
    "hip-hop": Project(
        name="hip-hop",
        bpm=95.0,
        patterns=[
            {"name": "kick", "dsl": "kick 4/4"},
            {"name": "snare", "dsl": "snare 2/8"},
            {"name": "hihat", "dsl": "hh 16x8"},
        ],
    ),
    "demo": Project(
        name="demo",
        bpm=128.0,
        patterns=[
            {"name": "main-kick", "dsl": "kick 4/4"},
            {"name": "hihat", "dsl": "hh 12x8"},
            {"name": "snare", "dsl": "snare 2/8"},
        ],
    ),
}


def get_template(name: str) -> Project:
    if name in TEMPLATES:
        import copy

        return copy.deepcopy(TEMPLATES[name])
    raise ValueError(f"Unknown template: {name}")


def list_projects() -> list[Path]:
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    return list(PROJECTS_DIR.glob("*.audx")) + list(PROJECTS_DIR.glob("*/project.audx"))


def init_project(
    name: str,
    parent: Path | None = None,
    template: str = "empty",
    git: bool = True,
) -> Path:
    """Scaffold a new project folder per spec §06 / §10.

    Creates ``<parent>/<name>/`` with ``project.audx``, ``stems/``, ``renders/``
    and (optionally) a ``git init``. Returns the project file path.
    """
    parent = parent or Path.cwd()
    project_dir = parent / name
    if project_dir.exists() and any(project_dir.iterdir()):
        raise FileExistsError(f"Project folder already exists and is non-empty: {project_dir}")
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "stems").mkdir(exist_ok=True)
    (project_dir / "renders").mkdir(exist_ok=True)

    project = get_template(template) if template != "empty" else Project(name=name)
    project.name = name
    project_path = project_dir / "project.audx"
    project.save(project_path)

    if git:
        try:
            subprocess.run(
                ["git", "init", "-q"],
                cwd=project_dir,
                check=False,
                capture_output=True,
                timeout=5,
            )
            (project_dir / ".gitignore").write_text("renders/\n*.wav\n*.mp3\n*.flac\n", encoding="utf-8")
        except (FileNotFoundError, subprocess.SubprocessError):
            # git missing or timed out -- not fatal
            pass

    return project_path


def diff_projects(a: Path, b: Path) -> list[str]:
    """Return a human-readable diff between two project files.

    Output is a list of lines matching the spec mock:
        ~ ch5/bass     gain  -4.0 -> -2.5  dB
        + ch7/pad      F#3 | sus 2 | reverb 0.4 0.3
        - ch8/fx       (deleted)
    """
    pa = Project.load(a)
    pb = Project.load(b)
    lines: list[str] = []

    if pa.bpm != pb.bpm:
        lines.append(f"~ bpm        {pa.bpm} → {pb.bpm}")
    if pa.time_sig != pb.time_sig:
        lines.append(f"~ time_sig   {pa.time_sig} → {pb.time_sig}")

    names_a = {p["name"]: p for p in pa.patterns}
    names_b = {p["name"]: p for p in pb.patterns}
    for name in sorted(set(names_a) | set(names_b)):
        in_a = name in names_a
        in_b = name in names_b
        if in_a and not in_b:
            lines.append(f"- {name:<10} (deleted)")
        elif in_b and not in_a:
            lines.append(f"+ {name:<10} {names_b[name].get('dsl', '')}")
        else:
            dsl_a = names_a[name].get("dsl", "")
            dsl_b = names_b[name].get("dsl", "")
            if dsl_a != dsl_b:
                lines.append(f"~ {name:<10} {dsl_a}  →  {dsl_b}")

    mix_a = {int(ch.get("channel", -1)): ch for ch in pa.mixer}
    mix_b = {int(ch.get("channel", -1)): ch for ch in pb.mixer}
    for ch in sorted(set(mix_a) | set(mix_b)):
        ca = mix_a.get(ch, {})
        cb = mix_b.get(ch, {})
        if ca.get("gain_db") != cb.get("gain_db"):
            lines.append(
                f"~ ch{ch}/gain   "
                f"{ca.get('gain_db', 0.0):+.1f} → {cb.get('gain_db', 0.0):+.1f} dB"
            )
        if ca.get("mute") != cb.get("mute"):
            lines.append(f"~ ch{ch}/mute   {ca.get('mute', False)} → {cb.get('mute', False)}")
    return lines

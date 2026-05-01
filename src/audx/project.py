"""Project save/load and templates."""
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from audx.config import PROJECTS_DIR
from audx.pattern import Pattern


@dataclass
class Project:
    name: str
    bpm: float = 120.0
    patterns: list[dict[str, Any]] = field(default_factory=list)
    # Future: mixer state, sample assignments, etc.
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def save(self, path: Path):
        """Save project to JSON file."""
        data = asdict(self)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: Path) -> "Project":
        """Load project from JSON file."""
        with open(path) as f:
            data = json.load(f)
        return cls(**data)

    def apply_to_engine(self):
        """Restore patterns into current pattern engine."""
        from audx.pattern import get_pattern_engine
        eng = get_pattern_engine()
        eng.set_bpm(self.bpm)
        eng.patterns.clear()
        for pdata in self.patterns:
            pat = Pattern(
                name=pdata['name'],
                dsl=pdata['dsl'],
                length_beats=pdata.get('length_beats', 4),
                channel=pdata.get('channel', 0),
                swing=pdata.get('swing', 0.0),
            )
            pat.parse_dsl()
            eng.add_pattern(pat)


# Template presets
TEMPLATES = {
    "empty": Project(name="empty", bpm=120.0),
    "techno": Project(
        name="techno",
        bpm=135.0,
        patterns=[
            {"name": "kick", "dsl": "kick 4/4"},
            {"name": "hihat", "dsl": "hh 8x8"},
            {"name": "clap", "dsl": "clap 2/4"},
        ]
    ),
    "hip-hop": Project(
        name="hip-hop",
        bpm=95.0,
        patterns=[
            {"name": "kick", "dsl": "kick 4/4"},
            {"name": "snare", "dsl": "snare 2/4"},
            {"name": "hihat", "dsl": "hh 16x8"},
        ]
    ),
    "demo": Project(
        name="demo",
        bpm=128.0,
        patterns=[
            {"name": "main-kick", "dsl": "kick 4/4"},
            {"name": "hihat", "dsl": "hh 12x8"},
            {"name": "snare", "dsl": "snare 2/4"},
        ]
    )
}

def get_template(name: str) -> Project:
    if name in TEMPLATES:
        # Return a copy
        import copy
        return copy.deepcopy(TEMPLATES[name])
    raise ValueError(f"Unknown template: {name}")

def list_projects() -> list[Path]:
    """List all .audx project files in projects dir."""
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    return list(PROJECTS_DIR.glob("*.audx"))

"""Local plugin discovery scaffolding.

No hosting yet. This deliberately only scans common plugin directories and
returns metadata. Actual AU/VST hosting needs a separate audio-safe bridge.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_PLUGIN_DIRS = [
    Path("/Library/Audio/Plug-Ins/Components"),
    Path("/Library/Audio/Plug-Ins/VST"),
    Path("/Library/Audio/Plug-Ins/VST3"),
    Path.home() / "Library/Audio/Plug-Ins/Components",
    Path.home() / "Library/Audio/Plug-Ins/VST",
    Path.home() / "Library/Audio/Plug-Ins/VST3",
]


@dataclass(frozen=True)
class PluginInfo:
    name: str
    path: Path
    kind: str


def scan_plugins(paths: list[Path] | None = None) -> list[PluginInfo]:
    roots = paths or DEFAULT_PLUGIN_DIRS
    found: list[PluginInfo] = []
    suffix_map = {
        ".component": "AU",
        ".vst": "VST",
        ".vst3": "VST3",
    }
    for root in roots:
        if not root.exists():
            continue
        for suffix, kind in suffix_map.items():
            for item in root.glob(f"*{suffix}"):
                found.append(PluginInfo(name=item.stem, path=item, kind=kind))
    return sorted(found, key=lambda plugin: (plugin.kind, plugin.name.lower()))

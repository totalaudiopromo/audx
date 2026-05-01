"""Configuration and constants."""
import os
from pathlib import Path
from typing import Final

HOME: Final = Path.home()
CONFIG_DIR: Final = HOME / "Library" / "Application Support" / "audx"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

SAMPLES_DIR: Final = HOME / "Samples"
PROJECTS_DIR: Final = HOME / "Documents" / "audx"
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

# Audio
SAMPLE_RATE: Final = 44100
CHANNELS: Final = 2
BLOCK_SIZE: Final = 512  # ~11ms @ 44.1k

# Mixer
CHANNELS_COUNT: Final = 16

# Pattern
DEFAULT_BPM: Final = 128

# Runtime BPM (overridable via AUDX_BPM env)
AUDX_BPM: Final = int(os.getenv("AUDX_BPM", str(DEFAULT_BPM)))
DEFAULT_PPQN: Final = 960  # pulses per quarter note (MIDI resolution)

# UI
THEME = {
    "primary": "#d4a574",    # warm amber (sink-inspired)
    "secondary": "#a8c087",  # sage green
    "accent": "#e8a6c2",     # muted pink
    "background": "#111111",
    "surface": "#1e1e1e",
    "text": "#e0e0e0",
    "text-muted": "#888888",
    "border": "#333333",
}

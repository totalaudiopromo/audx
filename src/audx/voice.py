"""Voice-control stub (spec §11 `audx voice`).

A minimal scaffold so the command is wired and the CLI surface matches the
spec. Real wake-word + whisper.cpp integration is intentionally out of scope
for the first land -- but the public surface is here so callers can write
against it now and we can swap implementations later.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class VoiceStatus:
    available: bool
    detail: str


def status() -> VoiceStatus:
    """Probe whether on-device voice control is reachable."""
    try:
        import importlib

        importlib.import_module("whispercpp")  # type: ignore[import-not-found]
        return VoiceStatus(True, "whispercpp installed")
    except ImportError:
        return VoiceStatus(False, "install whispercpp for on-device transcription")


COMMANDS: dict[str, Callable[[], None]] = {
    # Filled in by the TUI/CLI when the listener is started.
}


def parse_intent(transcript: str) -> tuple[str, list[str]]:
    """Map a transcript like 'mute the snare' to (verb, args)."""
    tokens = [token for token in transcript.lower().split() if token not in {"the", "a", "an", "please"}]
    if not tokens:
        return ("", [])
    return (tokens[0], tokens[1:])

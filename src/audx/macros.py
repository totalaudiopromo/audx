"""Vim-style macro registers (spec §11 `qa`...`q`...`@a`).

The TUI records every keystroke between `q<reg>` and `q` into a named register.
`@<reg>` replays the recorded keystrokes. Registers persist to the project
file so a fill recorded today survives a restart tomorrow.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MacroStore:
    """In-memory macro registers indexed by single-character name."""

    registers: dict[str, list[str]] = field(default_factory=dict)
    recording: str | None = None
    _buffer: list[str] = field(default_factory=list)

    def start(self, register: str) -> None:
        register = (register or "").strip().lower()[:1]
        if not register:
            return
        self.recording = register
        self._buffer = []

    def stop(self) -> None:
        if self.recording is None:
            return
        self.registers[self.recording] = list(self._buffer)
        self.recording = None
        self._buffer = []

    def capture(self, key: str) -> None:
        if self.recording is not None:
            self._buffer.append(key)

    def replay(self, register: str) -> list[str]:
        return list(self.registers.get((register or "").lower()[:1], []))

    def to_dict(self) -> dict[str, list[str]]:
        return {name: list(keys) for name, keys in self.registers.items()}

    @classmethod
    def from_dict(cls, data: dict[str, list[str]] | None) -> MacroStore:
        store = cls()
        for name, keys in (data or {}).items():
            store.registers[name[:1].lower()] = list(keys)
        return store

"""File-watch for project.audx hot-reload (spec §08, §03 file-edit path).

Polls the file's mtime and re-applies the project to the running pattern
engine on change. Stdlib-only; no `notify`/`watchdog` dependency added.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

from audx.project import Project


class FileWatcher:
    """Polling watcher; calls ``on_change(path, project)`` after a save."""

    def __init__(
        self,
        path: Path,
        on_change: Callable[[Path, Project], None],
        interval: float = 0.5,
    ) -> None:
        self.path = Path(path)
        self.on_change = on_change
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._mtime: float | None = self.path.stat().st_mtime if self.path.exists() else None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="audx-watch", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                if self.path.exists():
                    mtime = self.path.stat().st_mtime
                    if self._mtime is None or mtime > self._mtime:
                        self._mtime = mtime
                        project = Project.load(self.path)
                        self.on_change(self.path, project)
            except Exception:  # pragma: no cover - watcher must never crash
                pass
            self._stop.wait(self.interval)

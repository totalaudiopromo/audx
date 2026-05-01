"""Minimal audx local daemon.

This is intentionally tiny: it keeps process state alive and exposes JSON HTTP
endpoints. It is not an audio server replacement yet, but it solves the worst
CLI limitation: separate commands can share state through one local process.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from audx.pattern import Pattern, get_pattern_engine
from audx.project import Project

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5744


class AudxDaemonHandler(BaseHTTPRequestHandler):
    server_version = "audxd/0.1"

    def do_GET(self) -> None:
        if self.path == "/status":
            engine = get_pattern_engine()
            self._json({"ok": True, "bpm": engine.bpm, "patterns": list(engine.patterns)})
            return
        self._json({"error": "not found"}, status=404)

    def do_POST(self) -> None:
        payload = self._read_json()
        if self.path == "/pattern":
            pattern = Pattern(name=payload["name"], dsl=payload["dsl"])
            pattern.parse_dsl()
            get_pattern_engine().add_pattern(pattern)
            self._json({"ok": True, "steps": len(pattern.steps)})
            return
        if self.path == "/save":
            path = Path(payload["path"]).expanduser()
            engine = get_pattern_engine()
            project = Project(
                name=payload.get("name") or path.stem,
                bpm=engine.bpm,
                patterns=[
                    {"name": name, "dsl": pattern.dsl, "length_beats": pattern.length_beats}
                    for name, pattern in engine.patterns.items()
                ],
            )
            project.save(path)
            self._json({"ok": True, "path": str(path)})
            return
        self._json({"error": "not found"}, status=404)

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("content-length", "0"))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_daemon(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    server = ThreadingHTTPServer((host, port), AudxDaemonHandler)
    print(f"audxd listening on http://{host}:{port}")
    server.serve_forever()

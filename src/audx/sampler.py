"""Sample library management and search."""

from __future__ import annotations

import json
from pathlib import Path

import soundfile as sf

_global_library: SampleLibrary | None = None


def get_sample_library() -> SampleLibrary:
    global _global_library
    if _global_library is None:
        from audx.config import SAMPLES_DIR

        _global_library = SampleLibrary(SAMPLES_DIR)
    return _global_library


class SampleLibrary:
    """Tiny file-backed sample index.

    Important: the method is named ``build_index``. The previous implementation
    had ``self.index`` and ``def index()`` with the same name, so the method was
    overwritten by the dict at runtime and ``audx samples-index`` crashed.
    """

    def __init__(self, root_dir: Path | str):
        self.root = Path(root_dir)
        self.index_path = self.root / ".audx-index.json"
        self.samples: dict[str, dict] = {}
        self.samples_by_tag: dict[str, list[str]] = {}

    @property
    def index(self) -> dict[str, dict]:
        """Backward-compatible access for old callers/tests."""
        return self.samples

    def build_index(self, recursive: bool = True) -> dict[str, dict]:
        self.samples = {}
        self.samples_by_tag = {}
        if not self.root.exists():
            self.root.mkdir(parents=True, exist_ok=True)
        extensions = {".wav", ".mp3", ".flac", ".ogg", ".aiff", ".aif"}
        pattern = "**/*" if recursive else "*"
        for path in self.root.glob(pattern):
            if not path.is_file() or path.suffix.lower() not in extensions:
                continue
            try:
                with sf.SoundFile(str(path)) as file_handle:
                    rel = str(path.relative_to(self.root))
                    tags = self._extract_tags(path.stem)
                    self.samples[rel] = {
                        "path": str(path),
                        "name": path.name,
                        "duration": file_handle.frames / file_handle.samplerate,
                        "sr": file_handle.samplerate,
                        "channels": file_handle.channels,
                        "tags": tags,
                    }
                    for tag in tags:
                        self.samples_by_tag.setdefault(tag, []).append(rel)
            except Exception as exc:  # pragma: no cover - malformed user audio
                print(f"Failed to index {path}: {exc}")
        self.save_index()
        return self.samples

    def save_index(self) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(
            json.dumps(
                {
                    "index": self.samples,
                    "by_tag": self.samples_by_tag,
                    "root": str(self.root),
                },
                indent=2,
            )
        )

    def load_index(self) -> None:
        if not self.index_path.exists():
            self.build_index()
            return
        data = json.loads(self.index_path.read_text())
        self.samples = data.get("index", {})
        self.samples_by_tag = data.get("by_tag", {})

    @staticmethod
    def _extract_tags(filename: str) -> list[str]:
        name = filename.lower()
        for sep in ["_", "-", "."]:
            name = name.replace(sep, " ")
        return [
            token
            for token in name.split()
            if not token.isdigit() and token not in {"sample", "loop", "one", "shot"}
        ]

    def search(self, query: str = "", limit: int = 20) -> list[dict]:
        if not self.samples:
            self.load_index()
        query_lower = query.lower().strip()
        results: list[tuple[int, dict]] = []
        for meta in self.samples.values():
            score = 1 if not query_lower else 0
            if query_lower and query_lower in meta["name"].lower():
                score += 10
            if query_lower and any(query_lower in tag for tag in meta["tags"]):
                score += 5
            if score > 0:
                results.append((score, meta))
        results.sort(reverse=True, key=lambda item: item[0])
        return [meta for _, meta in results[:limit]]

    def resolve(self, sample_name: str) -> Path | None:
        if not self.samples:
            self.load_index()
        query = sample_name.lower()
        for meta in self.samples.values():
            if meta["name"].lower() == query or Path(meta["name"]).stem.lower() == query:
                return Path(meta["path"])
        matches = self.search(query=sample_name, limit=1)
        if matches:
            return Path(matches[0]["path"])
        return None

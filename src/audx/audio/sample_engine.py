"""
Sample library management: indexing, tag search, playback voices.
"""
import sqlite3
from pathlib import Path

import numpy as np
import soundfile as sf


class SampleLibrary:
    """Index and access your sample collection."""
    def __init__(self, root: Path):
        self.root = root
        self.db_path = Path.home() / ".config" / "audx" / "samples.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._cache: dict[Path, np.ndarray] = {}

    def _init_db(self):
        conn = sqlite3.connect(str(self.db_path))
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS samples (
                id INTEGER PRIMARY KEY,
                path TEXT UNIQUE,
                name TEXT,
                duration REAL,
                channels INTEGER,
                sample_rate INTEGER,
                tags TEXT,
                favourite INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()

    def index(self, path: Path | None = None, recursive: bool = True):
        """Scan `path` (or self.root) for audio files and add to index."""
        root = path or self.root
        for ext in ('*.wav', '*.flac', '*.mp3', '*.aif', '*.aiff', '*.ogg'):
            files = root.rglob(ext) if recursive else root.glob(ext)
            for f in files:
                self._add_file(f)

    def _add_file(self, path: Path):
        try:
            data, sr = sf.read(str(path), always_2d=False)
            duration = len(data) / sr
            name = path.stem
            tags = ""  # TODO: auto-tag by folder or folder structure
            conn = sqlite3.connect(str(self.db_path))
            cur = conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO samples (path, name, duration, channels, sample_rate, tags)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (str(path), name, duration, data.shape[1] if data.ndim > 1 else 1, sr, tags))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error indexing {path}: {e}")

    def search(self, query: str = "", tags: list[str] | None = None, limit: int = 20) -> list[dict]:
        """Search samples by name/tags."""
        conn = sqlite3.connect(str(self.db_path))
        cur = conn.cursor()
        sql = "SELECT id, path, name, duration, tags FROM samples WHERE 1=1"
        params: list[str | int] = []
        if query:
            sql += " AND name LIKE ?"
            params.append(f"%{query}%")
        if tags:
            for tag in tags:
                sql += " AND tags LIKE ?"
                params.append(f"%{tag}%")
        sql += " LIMIT ?"
        params.append(limit)
        cur.execute(sql, params)
        rows = cur.fetchall()
        conn.close()
        return [{"id": row[0], "path": row[1], "name": row[2], "duration": row[3], "tags": row[4]} for row in rows]

    def load(self, path: Path) -> np.ndarray:
        """Load sample data, caching."""
        p = Path(path)
        if p in self._cache:
            return self._cache[p]
        data, _sr = sf.read(str(p), always_2d=True)  # always stereo for mixing
        self._cache[p] = data
        return data

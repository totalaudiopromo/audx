"""Sample similarity using audio embeddings (lightweight)."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

import numpy as np


class Embedding(NamedTuple):
    path: str
    vector: np.ndarray


@dataclass
class Match:
    path: str
    distance: float


def _ensure_librosa():
    try:
        import librosa
        return librosa
    except ImportError as exc:
        raise ImportError("librosa required, install `[ai]` extras") from exc


def chroma_embedding(y: np.ndarray, sr: int, n_fft: int = 2048, hop: int = 512) -> np.ndarray:
    librosa = _ensure_librosa()
    chroma = librosa.feature.chroma_stft(y=y, sr=sr, n_fft=n_fft, hop_length=hop)
    return chroma.mean(axis=1)


def mfcc_embedding(y: np.ndarray, sr: int, n_mfcc: int = 13) -> np.ndarray:
    librosa = _ensure_librosa()
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=n_mfcc)
    return mfcc[:4].mean(axis=1)


def compute_embedding(audio_path: Path) -> np.ndarray:
    import soundfile as sf
    _ensure_librosa()
    y, sr = sf.read(str(audio_path))
    if y.ndim > 1:
        y = y.mean(axis=1)
    y = y / (np.linalg.norm(y) + 1e-8)

    c = chroma_embedding(y, sr)
    m = mfcc_embedding(y, sr)
    vec = np.concatenate([c, m]).astype(np.float32)
    vec = vec / (np.linalg.norm(vec) + 1e-8)
    return vec


def cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    return 1.0 - float(np.dot(a, b))


class EmbeddingIndex:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS embeddings (
                   path TEXT PRIMARY KEY,
                   vec BLOB NOT NULL
               )"""
        )
        self.conn.commit()

    def add(self, path: str, vec: np.ndarray) -> None:
        blob = vec.tobytes()
        self.conn.execute("INSERT OR REPLACE INTO embeddings(path, vec) VALUES(?, ?)", (path, blob))
        self.conn.commit()

    def search(self, query: np.ndarray, limit: int = 5) -> list[Match]:
        cur = self.conn.execute("SELECT path, vec FROM embeddings")
        results: list[Match] = []
        for row in cur:
            path, blob = row
            vec = np.frombuffer(blob, dtype=np.float32)
            dist = cosine_distance(query, vec)
            results.append(Match(path=path, distance=dist))
        results.sort(key=lambda m: m.distance)
        return results[:limit]

    @classmethod
    def load_or_build(cls, samples_dir: Path) -> EmbeddingIndex:
        index = cls(samples_dir / ".audx-embeddings.db")
        cur = index.conn.execute("SELECT COUNT(*) FROM embeddings")
        count = cur.fetchone()[0]
        if count == 0:
            print(f"[AI] Indexing {samples_dir} …")
            wavs = list(samples_dir.rglob("*.wav")) + list(samples_dir.rglob("*.mp3"))
            for wav in wavs:
                try:
                    vec = compute_embedding(wav)
                    index.add(str(wav), vec)
                except Exception as exc:
                    print(f"  skip {wav.name}: {exc}")
            count = index.conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
            print(f"[AI] Indexed {count} samples")
        return index

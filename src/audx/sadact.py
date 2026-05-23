"""Sadact Finisher bridge."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import requests  # type: ignore[import-untyped]

DEFAULT_URL = "http://localhost:5742"


@dataclass(frozen=True)
class SadactStatus:
    available: bool
    detail: str


class SadactClient:
    def __init__(self, base_url: str = DEFAULT_URL, api_key: str | None = None, timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.getenv("SADACT_FINISHER_API_KEY")
        self.timeout = timeout

    def status(self) -> SadactStatus:
        try:
            response = requests.get(f"{self.base_url}/status", timeout=5)
            if response.ok:
                return SadactStatus(True, response.text[:300])
            return SadactStatus(False, f"HTTP {response.status_code}: {response.text[:300]}")
        except Exception as exc:
            return SadactStatus(False, str(exc))

    def process(self, stems_zip: Path, output_path: Path | None = None, preset: str = "loudness-14") -> Path:
        if not stems_zip.exists():
            raise FileNotFoundError(stems_zip)
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        with stems_zip.open("rb") as file_handle:
            response = requests.post(
                f"{self.base_url}/process",
                files={"file": file_handle},
                data={"preset": preset},
                headers=headers,
                timeout=self.timeout,
            )
        response.raise_for_status()
        output = output_path or stems_zip.with_name(f"{stems_zip.stem}-mastered.zip")
        output.write_bytes(response.content)
        return output

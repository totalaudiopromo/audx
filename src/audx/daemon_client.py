"""Client helpers for audxd."""

from __future__ import annotations

from typing import Any

import requests

DEFAULT_DAEMON_URL = "http://127.0.0.1:5744"


def daemon_status(base_url: str = DEFAULT_DAEMON_URL) -> dict[str, Any]:
    response = requests.get(f"{base_url.rstrip('/')}/status", timeout=3)
    response.raise_for_status()
    return response.json()


def daemon_add_pattern(name: str, dsl: str, base_url: str = DEFAULT_DAEMON_URL) -> dict[str, Any]:
    response = requests.post(
        f"{base_url.rstrip('/')}/pattern",
        json={"name": name, "dsl": dsl},
        timeout=3,
    )
    response.raise_for_status()
    return response.json()


def daemon_save(path: str, name: str | None = None, base_url: str = DEFAULT_DAEMON_URL) -> dict[str, Any]:
    payload: dict[str, Any] = {"path": path}
    if name:
        payload["name"] = name
    response = requests.post(f"{base_url.rstrip('/')}/save", json=payload, timeout=3)
    response.raise_for_status()
    return response.json()

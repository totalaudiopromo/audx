"""Secret storage for the AI key (spec §06 `audx ai key`).

Prefers the macOS keychain via the ``security`` binary. Falls back to an
xdg-style file under ``CONFIG_DIR/secrets.json`` with 0o600 perms, so the
key is at least not living in the project file.
"""

from __future__ import annotations

import json
import os
import platform
import stat
import subprocess

from audx.config import CONFIG_DIR

SERVICE = "audx"
FALLBACK_PATH = CONFIG_DIR / "secrets.json"


def set_key(account: str, secret: str) -> str:
    """Store a secret. Returns the storage backend used."""
    if platform.system() == "Darwin":
        try:
            subprocess.run(
                [
                    "security", "add-generic-password",
                    "-s", SERVICE,
                    "-a", account,
                    "-w", secret,
                    "-U",
                ],
                check=True,
                capture_output=True,
                timeout=5,
            )
            return "macos-keychain"
        except (FileNotFoundError, subprocess.SubprocessError):
            pass
    return _file_set(account, secret)


def get_key(account: str) -> str | None:
    if platform.system() == "Darwin":
        try:
            proc = subprocess.run(
                ["security", "find-generic-password", "-s", SERVICE, "-a", account, "-w"],
                check=True,
                capture_output=True,
                timeout=5,
            )
            return proc.stdout.decode("utf-8").strip()
        except (FileNotFoundError, subprocess.SubprocessError):
            pass
    return _file_get(account)


def _file_set(account: str, secret: str) -> str:
    FALLBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, str] = {}
    if FALLBACK_PATH.exists():
        try:
            data = json.loads(FALLBACK_PATH.read_text())
        except json.JSONDecodeError:
            data = {}
    data[account] = secret
    FALLBACK_PATH.write_text(json.dumps(data))
    try:
        os.chmod(FALLBACK_PATH, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    return f"file:{FALLBACK_PATH}"


def _file_get(account: str) -> str | None:
    if not FALLBACK_PATH.exists():
        return None
    try:
        data = json.loads(FALLBACK_PATH.read_text())
    except json.JSONDecodeError:
        return None
    value = data.get(account)
    return str(value) if value else None

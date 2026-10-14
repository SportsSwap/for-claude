"""Settings from environment variables, and checks on where client data lives."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

DEFAULT_CLIENT_CODE_PATTERN = r"^[A-Z0-9]{2,12}$"
# Folder names used by OneDrive, SharePoint/Teams libraries, Dropbox, Google Drive and iCloud.
_CLOUD_FOLDER = re.compile(
    r"^(onedrive.*|dropbox(\b.*)?|google ?drive.*|googledrive-.*|my drive|shared drives|icloud ?drive"
    r"|cloudstorage|.* - (shared )?documents)$", re.I)
_CLOUD_ENV = ("OneDrive", "OneDriveCommercial", "OneDriveConsumer")


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Settings:
    tra_home: Path
    store: str
    client_code_pattern: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "Settings":
        home = env.get("TRA_HOME", "").strip()
        if not home:
            raise ConfigError("TRA_HOME is not set. Run setup.ps1, or set it to a folder on this computer.")
        store = env.get("TRA_STORE", "local").strip().lower() or "local"
        if store not in ("local", "fyi"):
            raise ConfigError(f"TRA_STORE must be 'local' or 'fyi', not {store!r}")
        pattern = env.get("TRA_CLIENT_CODE_PATTERN", "").strip() or DEFAULT_CLIENT_CODE_PATTERN
        return cls(tra_home=Path(home), store=store, client_code_pattern=pattern)


def _cloud_problem(where: str) -> str:
    return (f"TRA_HOME is inside a cloud-synced folder ({where}). Client data must stay on this "
            "computer (Privacy Act APP 8). Choose a local folder such as C:\\TaxAssistant.")


def check_tra_home(path: Path, env: Mapping[str, str] = os.environ) -> list[str]:
    """Problems that make a folder unsafe for client data. Empty means OK."""
    if not path.is_dir():
        return [f"TRA_HOME does not exist: {path}"]
    resolved = path.resolve()
    problems = []
    roots = [Path(env[name]).resolve() for name in _CLOUD_ENV if env.get(name)]
    synced_root = next((root for root in roots if resolved == root or root in resolved.parents), None)
    if synced_root is not None:
        problems.append(_cloud_problem(str(synced_root)))
    else:
        for part in resolved.parts:
            if _CLOUD_FOLDER.match(part):
                problems.append(_cloud_problem(part))
                break
    for folder in (resolved, *resolved.parents):
        if (folder / ".git").exists():
            problems.append(
                f"TRA_HOME is inside a git repository ({folder}). Client data must never sit in version control.")
            break
    return problems


def validate_client_code(code: str, pattern: str) -> None:
    if not re.fullmatch(pattern, code or ""):
        raise ValueError(
            f"Client code {code!r} doesn't match {pattern}. Use the firm's client code (e.g. SMIT01), never a name.")

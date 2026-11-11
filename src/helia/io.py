"""Atomic JSON persistence and safe repository snapshots."""

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path


def native_path(path: Path) -> Path:
    """Use extended Windows paths for long temporary/cache directories."""
    if os.name != "nt":
        return path
    absolute = str(path.absolute())
    if absolute.startswith("\\\\?\\"):
        return path
    if absolute.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + absolute[2:])
    return Path("\\\\?\\" + absolute)


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def write_json(path: Path, value) -> None:
    path = native_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    fd, name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True, default=str)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


IGNORE = {".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".env", "runs"}


def snapshot(source: Path, destination: Path) -> None:
    """Copy ordinary files only; never follow links outside a target."""

    def ignore(directory, names):
        return [n for n in names if n in IGNORE or Path(directory, n).is_symlink()]

    shutil.copytree(source, destination, ignore=ignore, dirs_exist_ok=True)


def tree_hash(root: Path) -> str:
    files = {}
    for p in sorted(root.rglob("*")):
        if (
            p.is_file()
            and not p.is_symlink()
            and not any(x in IGNORE for x in p.relative_to(root).parts)
        ):
            with p.open("rb") as stream:
                files[p.relative_to(root).as_posix()] = hashlib.file_digest(
                    stream, "sha256"
                ).hexdigest()
    return digest(files)

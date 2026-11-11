"""Bounded prerequisite checks and secret-free structured event records."""

import importlib.util
import json
import os
import shutil
import subprocess
import time
from pathlib import Path


def doctor(path: Path | None = None) -> dict:
    docker = shutil.which("docker")
    engine = False
    error = None
    if docker:
        try:
            result = subprocess.run([docker, "info", "--format", "{{.ServerVersion}}"],
                                    capture_output=True, text=True, timeout=10)
            engine = result.returncode == 0
            if not engine:
                error = "Docker engine unavailable; start Docker Desktop/Engine"
        except (OSError, subprocess.SubprocessError):
            error = "Docker engine check failed or timed out"
    dependencies = {name: importlib.util.find_spec(name) is not None
                    for name in ["pytest", "coverage", "cosmic_ray", "anthropic", "yaml"]}
    free = shutil.disk_usage(path or Path.cwd()).free
    return {"schema_version": 1, "docker_cli": docker, "docker_engine": engine,
            "docker_error": error, "api_key_set": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "dependencies": dependencies, "disk_free_bytes": free,
            "disk_ok": free >= 1024**3, "git": shutil.which("git"),
            "ready": engine and all(dependencies.values()) and free >= 1024**3}


def event(directory: Path, name: str, **fields) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"schema_version": 1, "time": time.time(),
                                 "event": name, **fields}) + "\n")

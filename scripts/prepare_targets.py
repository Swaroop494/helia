"""Fetch pinned targets without importing/installing/executing their code."""

import json
import subprocess
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    lock = json.loads((root / "targets/lock.json").read_text())
    for target in lock["targets"]:
        destination = root / "targets/checkouts" / target["name"]
        if destination.exists():
            actual = subprocess.check_output(
                ["git", "-C", str(destination), "rev-parse", "HEAD"], text=True
            ).strip()
            if actual != target["commit"]:
                raise RuntimeError(f"Existing checkout differs: {destination}; left unchanged")
            continue
        subprocess.run(
            [
                "git",
                "clone",
                "--no-checkout",
                "--filter=blob:none",
                target["url"],
                str(destination),
            ],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(destination), "checkout", "--detach", target["commit"]], check=True
        )
        print(destination)


if __name__ == "__main__":
    main()

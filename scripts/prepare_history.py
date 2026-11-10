"""Prepare the pinned Toolz historical fix checkout without altering the main target."""

import subprocess
from pathlib import Path

FIX = "c696ac6f3c2962b370fe8dda78c64cf2564e1457"


def main():
    root = Path(__file__).resolve().parents[1]
    destination = root / "targets/checkouts/toolz-history"
    if not destination.exists():
        subprocess.run(
            [
                "git",
                "clone",
                "--no-checkout",
                "--filter=blob:none",
                "https://github.com/pytoolz/toolz.git",
                str(destination),
            ],
            check=True,
        )
        subprocess.run(["git", "-C", str(destination), "checkout", "--detach", FIX], check=True)
    actual = subprocess.check_output(
        ["git", "-C", str(destination), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual != FIX:
        raise RuntimeError("Historical checkout differs; left unchanged")
    print(destination)


if __name__ == "__main__":
    main()

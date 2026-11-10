"""Fail CI unless the curated generated test detects the reverted Toolz bug."""

import json
from pathlib import Path


def main():
    evidence = json.loads(
        Path("targets/history/toolz-merge-with-evidence.json").read_text(encoding="utf-8")
    )
    if not evidence["confirmed"]:
        raise SystemExit(
            "Historical bug verification did not reproduce a fixed/pass, reverted/fail result"
        )
    print("Toolz historical bug confirmed by stable differential test")


if __name__ == "__main__":
    main()

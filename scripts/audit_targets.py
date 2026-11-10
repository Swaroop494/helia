"""Read-only static target qualification; no imports of target packages."""

import json
from pathlib import Path

from helia.io import write_json
from helia.repo_index import build_index


def main():
    root = Path(__file__).resolve().parents[1]
    targets = json.loads((root / "targets/lock.json").read_text(encoding="utf-8"))["targets"]
    audit = []
    for target in targets:
        checkout = root / "targets/checkouts" / target["name"]
        index = build_index(checkout, target["source_dirs"])
        loc = sum(
            len((checkout / file).read_text(encoding="utf-8").splitlines()) for file in index.files
        )
        license_file = next(checkout.glob("LICENSE*"))
        license_text = license_file.read_text(encoding="utf-8")
        audit.append(
            {
                "name": target["name"],
                "commit": target["commit"],
                "source_lines": loc,
                "within_size_range": 1000 <= loc <= 10000,
                "files": len(index.files),
                "regions": len(index.regions),
                "parse_errors": index.parse_errors,
                "license_file": license_file.name,
                "license": target["license_expected"],
                "license_text": license_text,
                "suite_timing": "pending Docker",
                "repeatability": "pending Docker",
            }
        )
    write_json(root / "targets/static-audit.json", audit)
    for item in audit:
        print(
            f"{item['name']}: {item['source_lines']} source lines; {item['license']}; Docker qualification pending"
        )


if __name__ == "__main__":
    main()

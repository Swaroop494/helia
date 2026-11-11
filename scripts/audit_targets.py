"""Read-only static target qualification; no imports of target packages."""

import argparse
import json
from pathlib import Path

from helia.io import write_json
from helia.repo_index import build_index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("configs", type=Path, nargs="*")
    parser.add_argument("--output", type=Path, default=Path("targets/audit.json"))
    args = parser.parse_args()
    if args.configs:
        from helia.audit import audit_target
        from helia.controller.config import load_config
        from helia.executor import DockerExecutor
        from helia.fakes import FakeExecutor

        records = []
        for path in args.configs:
            config = load_config(path.resolve())
            try:
                executor = (FakeExecutor() if config.backend == "fake" else DockerExecutor(
                    config.image, config.source_dirs, config.tests, config.timeout_s, config.workers
                ))
                records.append(audit_target(config, executor))
            except (RuntimeError, OSError, ValueError) as exc:
                records.append({"repo": str(config.repo), "error": str(exc)})
            write_json(args.output, records)
        return
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

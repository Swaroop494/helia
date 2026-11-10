"""Docker-only target qualification: original suite repetition, coverage and timing."""

from pathlib import Path

from helia.controller.config import load_config
from helia.executor import DockerExecutor
from helia.io import write_json


def main():
    root = Path(__file__).resolve().parents[1]
    records = []
    for name in ["cachetools", "toolz", "tabulate"]:
        config = load_config(root / "configs" / f"repo-{name}.yaml")
        executor = DockerExecutor(
            config.image, config.source_dirs, config.tests, config.timeout_s, config.workers
        )
        results = [executor.run(config.repo, {}) for _ in range(3)]
        record = {
            "name": name,
            "image_id": executor.image,
            "qualified": all(r.outcome == "pass" and r.duration_s <= 60 for r in results),
            "runs": [r.model_dump() for r in results],
        }
        records.append(record)
        write_json(root / "targets/runtime-audit.json", records)
        print(f"{name}: {'qualified' if record['qualified'] else 'needs investigation'}")


if __name__ == "__main__":
    main()

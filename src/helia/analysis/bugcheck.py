"""Differential historical-bug checks for saved arm/seed test suites."""

import json
import subprocess

from helia.analysis.history import verify_fix
from helia.io import tree_hash, write_json


def bugcheck(config, commit, run_dir, executor, output):
    manifest = json.loads((run_dir / "manifest.json").read_text())
    if manifest["synthetic"]:
        raise ValueError("Synthetic generated suites cannot establish historical bug findings")
    if manifest["target_hash"] != tree_hash(config.repo):
        raise ValueError("Bugcheck target differs from the generation target")
    records = []
    for seed in config.seeds:
        for arm in config.arms:
            directory = run_dir / f"seed-{seed}" / arm
            entry = {"arm": arm, "seed": seed}
            if not (directory / "complete.json").exists():
                entry["error"] = "No completed arm; generate or resume it first"
            else:
                path = directory / "generated.json"
                try:
                    generated = json.loads(path.read_text()) if path.exists() else {}
                    if arm != "repo" and not generated:
                        entry["error"] = "Arm has no accepted generated tests"
                    else:
                        entry["result"] = verify_fix(config.repo, commit, generated,
                                                     executor, config.reruns)
                except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
                    entry["error"] = str(exc)
            records.append(entry)
            write_json(output, {"schema_version": 1, "fix_commit": commit, "arms": records})
    return output

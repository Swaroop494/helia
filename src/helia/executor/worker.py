"""Container entry point. This file is copied into the immutable runner image."""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def main():
    job = json.loads(Path("/input/job.json").read_text())
    root = Path("/work/repo")
    shutil.copytree("/input/repo", root)
    os.chdir(root)
    os.environ["PYTHONPATH"] = os.pathsep.join([str(root), str(root / "src"), "/opt/helia"])
    action = job.get("action", "test")
    if action == "discover":
        from cosmic_ray.commands.init import init
        from cosmic_ray.work_db import WorkDB, use_db

        records = []
        for i, file in enumerate(job["files"]):
            config = Path(f"/work/cosmic-{i}.toml")
            config.write_text(
                "[cosmic-ray]\nmodule-path = "
                + json.dumps(file)
                + '\ntimeout = 30\nexcluded-modules = []\ntest-command = "python -m pytest"\n'
                '[cosmic-ray.distributor]\nname = "local"\n'
            )
            database = Path(f"/work/session-{i}.sqlite")
            with use_db(database) as db:
                init([Path(file)], db, {})
            with use_db(database, WorkDB.Mode.open) as db:
                for work in db.work_items:
                    spec = work.mutations[0]
                    records.append(
                        {
                            "file": str(spec.module_path),
                            "line": spec.start_pos[0],
                            "operator": spec.operator_name,
                            "occurrence": spec.occurrence,
                            "operator_args": getattr(spec, "operator_args", {}),
                        }
                    )
        Path("/output/mutants.json").write_text(json.dumps(records))
        return
    mutant = job.get("mutant")
    if mutant:
        from cosmic_ray.mutating import apply_mutation
        from cosmic_ray.plugins import get_operator

        _, changed = apply_mutation(
            Path(mutant["file"]),
            get_operator(mutant["operator"])(**mutant["operator_args"]),
            mutant["occurrence"],
        )
        if changed is None:
            raise RuntimeError("Cosmic Ray did not apply the requested mutation")
    for name, source in job.get("generated", {}).items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    # coverage.py interprets source entries as modules/directories, not .py files.
    # Measure the copied checkout, then retain only configured production paths.
    Path("/work/coveragerc").write_text("[run]\nbranch = True\nsource = .\n")
    command = [
        sys.executable,
        "-m",
        "coverage",
        "run",
        "--rcfile=/work/coveragerc",
        "-m",
        "pytest",
        "-p",
        "helia_plugin",
        "-q",
        "--tb=short",
        *job["tests"],
    ]
    started = time.monotonic()
    try:
        process = subprocess.run(command, capture_output=True, text=True, timeout=job["timeout_s"])
    except subprocess.TimeoutExpired:
        Path("/output/result.json").write_text(
            json.dumps(
                {
                    "target": "mutant" if mutant else "original",
                    "mutant_id": mutant["id"] if mutant else None,
                    "outcome": "timeout",
                    "duration_s": time.monotonic() - started,
                    "output": "Pytest exceeded its wall-time limit",
                }
            )
        )
        return
    result = (
        json.loads(Path("/work/pytest.json").read_text())
        if Path("/work/pytest.json").exists()
        else {}
    )
    code = process.returncode
    failures = result.get("failures", [])
    if code == 0:
        outcome = "pass"
    elif code == 1:
        outcome = (
            "assert_fail" if failures and all(f["assertion"] for f in failures) else "exception"
        )
    else:
        outcome = "no_tests" if code == 5 else "infra_error"
    contexts, statements = {}, {}
    from coverage import Coverage

    cov = Coverage(config_file="/work/coveragerc")
    cov.load()
    data = cov.get_data()
    for measured in sorted(data.measured_files()):
        path = Path(measured)
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            continue
        if not any(relative == s or relative.startswith(s.rstrip("/") + "/") for s in job["source_dirs"]):
            continue
        contexts[relative] = {str(k): v for k, v in data.contexts_by_lineno(measured).items()}
        statements[relative] = cov.analysis2(measured)[1]
    payload = {
        "target": "mutant" if mutant else "original",
        "mutant_id": mutant["id"] if mutant else None,
        "outcome": outcome,
        "duration_s": time.monotonic() - started,
        "output": (process.stdout + process.stderr)[-16000:],
        "failures": failures,
        "contexts": contexts,
        "statements": statements,
        "test_outcomes": result.get("test_outcomes", {}),
    }
    Path("/output/result.json").write_text(json.dumps(payload))


if __name__ == "__main__":
    main()

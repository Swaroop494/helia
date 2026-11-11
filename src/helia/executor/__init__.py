"""M3: bounded Docker worker pool; fresh filesystem and process tree for each job."""

import json
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath

from contracts.models import ExecResult, Mutant, Outcome
from helia.io import digest, snapshot, write_json
from helia.repo_index import region_for, select_tests


class DockerExecutor:
    """No host execution fallback. A pool slot creates a new disposable container."""

    def __init__(
        self,
        image: str,
        source_dirs: list[str],
        tests: list[str],
        timeout_s: float = 60,
        workers: int = 2,
        memory: str = "1g",
    ):
        self.image, self.source_dirs, self.tests = image, source_dirs, tests
        self.timeout_s, self.workers, self.memory = timeout_s, workers, memory
        self.slots = threading.BoundedSemaphore(workers)
        if not shutil.which("docker"):
            raise RuntimeError(
                "Docker is required. Install Docker Desktop with WSL2 or Docker Engine."
            )
        inspected = subprocess.run(
            ["docker", "image", "inspect", image], check=True, capture_output=True, text=True,
            timeout=15,
        )
        self.image = json.loads(inspected.stdout)[0]["Id"]

    def _job(self, root: Path, job: dict, output_name: str):
        for attempt in range(3):
            try:
                return self._job_once(root, job, output_name)
            except (RuntimeError, OSError, subprocess.TimeoutExpired):
                if attempt == 2:
                    raise
                time.sleep(0.25 * 2 ** attempt)
        raise AssertionError("unreachable")

    def _job_once(self, root: Path, job: dict, output_name: str):
        with self.slots, tempfile.TemporaryDirectory(prefix="helia-") as directory:
            base = Path(directory)
            incoming, outgoing = base / "input", base / "output"
            incoming.mkdir()
            outgoing.mkdir()
            snapshot(root, incoming / "repo")
            write_json(incoming / "job.json", job)
            # The worker is UID 65534. mkstemp creates job.json as 0600, so
            # explicitly grant read access before mounting input read-only.
            incoming.chmod(0o755)
            (incoming / "job.json").chmod(0o644)
            name = "helia-" + uuid.uuid4().hex
            command = [
                "docker",
                "run",
                "--rm",
                "--name",
                name,
                "--network=none",
                "--read-only",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
                "--pids-limit=128",
                "--memory",
                self.memory,
                "--cpus=1",
                "--user=65534:65534",
                "--tmpfs=/tmp:rw,nosuid,nodev,size=128m,mode=1777",
                "--tmpfs=/work:rw,nosuid,nodev,size=512m,mode=1777",
                "--mount",
                f"type=bind,source={incoming},target=/input,readonly",
                "--mount",
                f"type=bind,source={outgoing},target=/output",
                "--env=PYTHONDONTWRITEBYTECODE=1",
                "--env=PYTHONHASHSEED=0",
                self.image,
                "python",
                "/opt/helia/worker.py",
            ]
            # Output directory is disposable and contains no host secrets.
            outgoing.chmod(0o777)
            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=job.get("timeout_s", self.timeout_s) + 15,
                )
                path = outgoing / output_name
                if completed.returncode or not path.exists() or path.is_symlink():
                    raise RuntimeError("Container job failed: " + completed.stderr[-3000:])
                if path.stat().st_size > 50_000_000:
                    raise RuntimeError("Oversized worker result")
                return json.loads(path.read_text())
            finally:
                try:
                    subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=15)
                except (OSError, subprocess.TimeoutExpired):
                    pass

    def discover(self, root, index):
        records = self._job(
            root,
            {"action": "discover", "files": index.files, "timeout_s": max(300, self.timeout_s)},
            "mutants.json",
        )
        return [
            Mutant(
                **r,
                id=digest([r["file"], r["operator"], r["occurrence"]])[:24],
                region=region_for(index, r["file"], r["line"]),
            )
            for r in records
        ]

    def run(
        self,
        root: Path,
        generated: dict[str, str],
        mutant: Mutant | None = None,
        tests: list[str] | None = None,
    ) -> ExecResult:
        for name in generated:
            path = PurePosixPath(name.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts or ":" in name or path.suffix != ".py":
                raise ValueError("Generated tests must use relative Python file paths")
            if (root / path).exists():
                raise ValueError("Generated tests cannot overwrite repository files")
        started = time.monotonic()
        outcome: Outcome
        suite = list(self.tests)
        for name in sorted(generated):
            if not any(name == entry or name.startswith(entry.rstrip("/") + "/") for entry in suite):
                suite.append(name)
        try:
            value = self._job(
                root,
                {
                    "generated": generated,
                    "mutant": mutant.model_dump() if mutant else None,
                    "tests": tests if tests is not None else suite,
                    "source_dirs": self.source_dirs,
                    "timeout_s": self.timeout_s,
                },
                "result.json",
            )
            return ExecResult.model_validate(value)
        except subprocess.TimeoutExpired:
            outcome, output = "timeout", "Container exceeded wall-time limit"
        except (RuntimeError, ValueError, OSError) as exc:
            outcome, output = "infra_error", str(exc)
        return ExecResult(
            target="mutant" if mutant else "original",
            mutant_id=mutant.id if mutant else None,
            outcome=outcome,
            duration_s=time.monotonic() - started,
            output=output,
        )

    def evaluate(self, root, generated, mutants, baseline):
        if baseline.outcome != "pass":
            raise ValueError("Mutation evaluation requires a passing original suite")
        selections = {m.id: select_tests(baseline.contexts, m.file, m.line) for m in mutants}
        # A subset can fail even when the full suite passes (ordering/fixture dependencies).
        # Validate each distinct selection on original code before attributing a failure
        # to mutation. This cache is local to this exact generated-suite evaluation.
        subsets = {tuple(nodes) for nodes in selections.values() if nodes}
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            checked = list(
                pool.map(
                    lambda nodes: self.run(root, generated, tests=list(nodes)), sorted(subsets)
                )
            )
        valid_subsets = {
            nodes: result.outcome == "pass" for nodes, result in zip(sorted(subsets), checked)
        }

        def execute(mutant):
            tests = selections[mutant.id]
            if tests == []:
                return ExecResult(
                    target="mutant", mutant_id=mutant.id, outcome="no_tests", duration_s=0
                )
            if tests and not valid_subsets[tuple(tests)]:
                return ExecResult(
                    target="mutant",
                    mutant_id=mutant.id,
                    outcome="infra_error",
                    duration_s=0,
                    output="Selected test subset does not pass on original code",
                )
            return self.run(root, generated, mutant, tests)

        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            return list(pool.map(execute, mutants))

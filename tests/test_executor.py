import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from contracts.models import ExecResult, Mutant
from helia.executor import DockerExecutor


def make_executor(monkeypatch):
    monkeypatch.setattr("helia.executor.shutil.which", lambda _: "docker")
    monkeypatch.setattr(
        "helia.executor.subprocess.run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 0, '[{"Id":"sha256:pinned"}]', ""),
    )
    return DockerExecutor("image:tag", ["src"], ["tests"], workers=1)


def test_no_host_fallback(monkeypatch):
    monkeypatch.setattr("helia.executor.shutil.which", lambda _: None)
    with pytest.raises(RuntimeError, match="Docker is required"):
        DockerExecutor("image", ["src"], ["tests"])


def test_subset_must_pass_on_original(monkeypatch, tmp_path):
    executor = make_executor(monkeypatch)
    executor.run = Mock(
        return_value=ExecResult(target="original", outcome="assert_fail", duration_s=0)
    )
    m = Mutant(id="m", file="src/a.py", line=2, operator="op", occurrence=0, region="r")
    baseline = ExecResult(
        target="original",
        outcome="pass",
        duration_s=0,
        contexts={"src/a.py": {"2": ["tests/test_a.py::test_a|run"]}},
    )
    result = executor.evaluate(tmp_path, {}, [m], baseline)[0]
    assert result.outcome == "infra_error"
    assert executor.run.call_count == 1  # no mutant executes after the subset failed


def test_container_arguments_and_image_pinning(monkeypatch, tmp_path):
    executor = make_executor(monkeypatch)
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        if "--network=none" in command:
            mount = next(x for x in command if "target=/output" in x)
            path = Path(mount.split("source=", 1)[1].split(",target=", 1)[0])
            (path / "result.json").write_text(
                json.dumps({"target": "original", "outcome": "pass", "duration_s": 0})
            )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("helia.executor.subprocess.run", run)
    result = executor.run(tmp_path, {})
    assert result.outcome == "pass"
    command = commands[0]
    for flag in [
        "--network=none",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--pids-limit=128",
        "--user=65534:65534",
        "sha256:pinned",
    ]:
        assert flag in command
    assert commands[-1][:3] == ["docker", "rm", "-f"]


@pytest.mark.parametrize("name", ["../escape.py", "/tmp/evil.py", "C:/evil.py"])
def test_generated_paths_are_bounded(monkeypatch, tmp_path, name):
    executor = make_executor(monkeypatch)
    with pytest.raises(ValueError):
        executor.run(tmp_path, {name: "pass"})


def test_no_overwriting_existing_tests(monkeypatch, tmp_path):
    executor = make_executor(monkeypatch)
    (tmp_path / "test_original.py").write_text("pass")
    with pytest.raises(ValueError, match="overwrite"):
        executor.run(tmp_path, {"test_original.py": "pass"})

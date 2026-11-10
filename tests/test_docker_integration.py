"""Opt-in real sandbox smoke test; runs automatically on Linux CI."""

import os
from pathlib import Path

import pytest

from helia.analysis import killed
from helia.executor import DockerExecutor
from helia.mutants import sample
from helia.repo_index import build_index


@pytest.mark.skipif(not os.environ.get("HELIA_DOCKER_IMAGE"), reason="Docker image not configured")
def test_real_worker_original_coverage_mutants_and_isolation():
    root = Path(__file__).resolve().parents[1] / "examples/toy"
    executor = DockerExecutor(os.environ["HELIA_DOCKER_IMAGE"], ["toy.py"], ["tests"], workers=2)
    baseline = executor.run(root, {})
    assert baseline.outcome == "pass", baseline.output
    assert baseline.contexts["toy.py"]
    index = build_index(root, ["toy.py"])
    mutants = sample(executor.discover(root, index), 1, 10, 10)
    assert mutants
    results = executor.evaluate(root, {}, mutants, baseline)
    assert not any(r.outcome == "infra_error" for r in results)
    assert any(killed(r) for r in results)
    isolation = {
        "tests/test_sandbox.py": "import os, socket\ndef test_isolation():\n"
        " assert os.getuid() != 0\n assert not os.path.exists('/var/run/docker.sock')\n"
        " assert not os.access('/opt/helia/worker.py', os.W_OK)\n"
        " s=socket.socket(); s.settimeout(0.2)\n"
        " try:\n  s.connect(('1.1.1.1', 443))\n except OSError:\n  return\n"
        " finally:\n  s.close()\n assert False, 'network was available'\n"
    }
    assert executor.run(root, isolation).outcome == "pass"

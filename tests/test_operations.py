import pytest

from helia.fakes import FakeLLM
from helia.llm import AnthropicProvider, BudgetExceeded, CachedLLM


def test_doctor_is_bounded_and_does_not_expose_key(monkeypatch):
    import json
    import subprocess

    from helia.diagnostics import doctor

    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret-sentinel")
    monkeypatch.setattr("helia.diagnostics.shutil.which", lambda _: "docker")

    def timeout(*args, **kwargs):
        assert kwargs["timeout"] == 10
        raise subprocess.TimeoutExpired("docker", 10)

    monkeypatch.setattr("helia.diagnostics.subprocess.run", timeout)
    result = doctor()
    assert not result["ready"] and result["api_key_set"]
    assert "secret-sentinel" not in json.dumps(result)


@pytest.mark.parametrize("updates", [{"timeout_s": float("inf")}, {"budget_usd": float("nan")},
                                    {"seeds": [-1]}, {"source_dirs": []}, {"reruns": 100},
                                    {"max_tokens": 100000}])
def test_config_rejects_unbounded_or_invalid_values(tmp_path, updates):
    from pydantic import ValidationError

    from helia.controller.config import Config

    with pytest.raises(ValidationError):
        Config(repo=tmp_path, backend="fake", **updates)


def test_retries_reserve_each_attempt(tmp_path, monkeypatch):
    from helia.llm import TransientProviderError

    waits = []
    monkeypatch.setattr("helia.llm.time.sleep", waits.append)

    class Failing(FakeLLM):
        def complete(self, *args):
            raise TransientProviderError("ambiguous")

    llm = CachedLLM(Failing(), tmp_path / "cache", tmp_path / "ledger.json",
                    "fake", 1, 5, 1, 1)
    with pytest.raises(TransientProviderError):
        llm.complete("prompt")
    assert waits == [0.25, 0.5]
    assert len(llm.spend) == 3
    assert llm.cost > 0


def test_docker_transient_retry(monkeypatch):
    from helia.executor import DockerExecutor

    executor = DockerExecutor.__new__(DockerExecutor)
    calls = []

    def job(*args):
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("docker unavailable")
        return {"ok": True}

    monkeypatch.setattr(executor, "_job_once", job)
    monkeypatch.setattr("helia.executor.time.sleep", lambda _: None)
    assert executor._job(None, {}, "result.json") == {"ok": True}


def test_lock_only_reclaims_verified_local_dead_owner(tmp_path, monkeypatch):
    import json
    import os
    import socket

    from helia.locking import acquire_lock, process_dead

    assert not process_dead(os.getpid())
    path = tmp_path / ".lock"
    for owner in ["123", {"pid": 123, "host": "other-host"},
                  {"pid": 123, "host": socket.gethostname()}]:
        path.write_text(json.dumps(owner))
        monkeypatch.setattr("helia.locking.process_dead", lambda _: False)
        with pytest.raises(RuntimeError, match="not verified dead"):
            acquire_lock(path)
    monkeypatch.setattr("helia.locking.process_dead", lambda _: True)
    acquire_lock(path)
    assert json.loads(path.read_text())["pid"] == os.getpid()


def test_audit_reruns_and_preserves_licence(tmp_path):
    from contracts.models import ExecResult
    from helia.audit import audit_target
    from helia.controller.config import Config

    (tmp_path / "toy.py").write_text("def f(): return 1\n")
    (tmp_path / "LICENSE").write_text("licence evidence")

    class Executor:
        calls = 0

        def run(self, *_):
            self.calls += 1
            return ExecResult(target="original", duration_s=0.1,
                              outcome="pass" if self.calls < 4 else "assert_fail")

    executor = Executor()
    result = audit_target(Config(repo=tmp_path, source_dirs=["toy.py"], backend="fake"), executor)
    assert executor.calls == 4
    assert result["flaky"] and not result["qualified"]
    assert result["licence_texts"]["LICENSE"] == "licence evidence"


def test_matrix_is_cartesian_and_resumable(tmp_path, monkeypatch):
    from pathlib import Path

    from helia.controller.config import load_config
    from helia.controller.matrix import run_matrix

    config = load_config(Path(__file__).resolve().parents[1] / "configs/demo.yaml")
    config.runs = tmp_path / "runs"
    config.cache = tmp_path / "cache"
    config.arms = ["repo", "guided"]
    config.seeds = [0, 1]
    monkeypatch.setattr("helia.controller.matrix.load_config", lambda _: config)
    first = list(run_matrix([tmp_path / "fake.yaml"]))
    assert len(first) == 4
    assert len({r["run_dir"] for r in first}) == 4
    complete = list(config.runs.glob("*/seed-*/*/complete.json"))
    timestamps = [p.stat().st_mtime_ns for p in complete]
    assert list(run_matrix([tmp_path / "fake.yaml"])) == first
    assert [p.stat().st_mtime_ns for p in complete] == timestamps


def test_paid_provider_requires_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-key")
    with pytest.raises(RuntimeError, match="--live"):
        AnthropicProvider().complete("model", "prompt", {})
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        AnthropicProvider(live=True).complete("model", "prompt", {})


def test_shared_run_cap_survives_new_arm(tmp_path):
    shared = tmp_path / "run-spend.json"
    first = CachedLLM(FakeLLM(), tmp_path / "cache", tmp_path / "a/ledger.json",
                      "fake", 10, 10, 1, 1, run_spend_path=shared, run_budget_usd=0.004)
    first.complete("one")
    second = CachedLLM(FakeLLM(), tmp_path / "cache", tmp_path / "b/ledger.json",
                       "fake", 10, 10, 1, 1, run_spend_path=shared, run_budget_usd=0)
    with pytest.raises(BudgetExceeded, match="Run-wide"):
        second.complete("two")
    assert second.complete("one").cached

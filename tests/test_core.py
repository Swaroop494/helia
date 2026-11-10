from pathlib import Path

import pytest
from pydantic import ValidationError

from contracts.models import ExecResult, Mutant, Region
from helia.analysis import analyse, coverage_fraction, killed, triage
from helia.controller import run_experiment
from helia.controller.config import Config
from helia.controller.report import paired_interval
from helia.fakes import FakeExecutor, FakeLLM
from helia.generator import build_prompt, validate_response
from helia.io import snapshot, tree_hash
from helia.llm import BudgetExceeded, CachedLLM
from helia.mutants import sample
from helia.policy import Policy
from helia.repo_index import build_index, select_tests

ROOT = Path(__file__).resolve().parents[1]


def mutant(n=0, **updates):
    data = dict(
        id=str(n),
        file=f"module{n % 3}.py",
        line=1,
        region=f"r{n % 6}",
        operator="test",
        occurrence=n,
    )
    data.update(updates)
    return Mutant(**data)


def result(outcome="pass", **updates):
    return ExecResult(target="original", outcome=outcome, duration_s=0.1, **updates)


def test_sampling_reproducible_disjoint_and_capped():
    mutants = [mutant(i) for i in range(120)]
    a = sample(mutants, 42, 25, 8)
    b = sample(list(reversed(mutants)), 42, 25, 8)
    assert a == b
    assert len(a) == 24
    assert all(sum(m.file == f for m in a) <= 8 for f in {m.file for m in a})
    feedback = {m.id for m in a if m.split == "feedback"}
    heldout = {m.id for m in a if m.split == "heldout"}
    assert feedback and heldout and feedback.isdisjoint(heldout)
    assert sample(mutants, 43, 25, 8) != a


@pytest.mark.parametrize("file", ["../escape.py", "/etc/passwd", "C:/escape.py"])
def test_contract_rejects_escape(file):
    with pytest.raises(ValidationError):
        mutant(file=file)


def test_contract_rejects_schema_drift():
    with pytest.raises(ValidationError):
        result(schema_version=2)


def test_index_is_static(tmp_path):
    (tmp_path / "module.py").write_text(
        "raise RuntimeError('must not run')\nclass A:\n def f(self):\n  return helper()\ndef helper():\n return 1\n"
    )
    index = build_index(tmp_path, ["."])
    assert {r.name for r in index.regions} == {"A", "A.f", "helper"}
    assert "helper" in next(r for r in index.regions if r.name == "A.f").calls


def test_selection_handles_unknown_and_session_contexts():
    assert select_tests({}, "x.py", 2) is None
    assert select_tests({"x.py": {}}, "x.py", 2) == []
    assert select_tests({"x.py": {"2": [""]}}, "x.py", 2) is None
    assert select_tests(
        {"x.py": {"2": ["tests/t.py::test_a|run", "tests/t.py::test_a|setup"]}}, "x.py", 2
    ) == ["tests/t.py::test_a"]


@pytest.mark.parametrize("outcome", ["timeout", "infra_error", "no_tests", "pass"])
def test_non_kills(outcome):
    assert not killed(result(outcome))


def test_collection_failure_is_not_kill():
    assert not killed(result("exception", failures=[{"phase": "setup"}]))
    assert killed(result("exception", failures=[{"phase": "call"}]))


def test_heldout_rejected_by_analyser():
    m = mutant(split="heldout")
    r = ExecResult(target="mutant", mutant_id=m.id, outcome="pass", duration_s=0)
    with pytest.raises(ValueError, match="Held-out"):
        analyse([r], [m])


def test_mutant_source_cannot_enter_prompt():
    index = build_index(ROOT / "examples/toy", ["toy.py"])
    prompt = build_prompt(
        index,
        index.regions[0],
        "boundary",
        [{"mutated_source": "SECRET_MUTANT", "summary": "safe"}],
    )
    assert "SECRET_MUTANT" not in prompt
    assert "def clamp" in prompt


def test_dedupe_ignores_test_name_and_formatting():
    _, key, count = validate_response("def test_a():\n assert 1 == 1", set())
    assert count == 1
    with pytest.raises(ValueError, match="Duplicate"):
        validate_response("def test_b():\n    assert 1==1", {key})


@pytest.mark.parametrize("source", ["x = 1", "def test_a():\n pass", "def broken("])
def test_validator_rejects_unusable_tests(source):
    with pytest.raises((SyntaxError, ValueError)):
        validate_response(source, set())


def test_triage_does_not_confirm_without_ground_truth():
    failure = result("assert_fail", failures=[{"phase": "call", "type": "AssertionError"}])
    assert triage("test", [failure, failure]).status == "bug_lead"
    assert triage("test", [failure, result()]).status == "flaky"
    assert triage("test", [result("infra_error")]).status == "infrastructure"
    assert triage("test", [failure], lambda *_: {"expectation_wrong": True}).status == "invalid"


def test_policy_learns_and_explores():
    policy = Policy(1, exploration=0)
    regions = [Region(id="r", file="x.py", name="f", line=1, end_line=2, source="")]
    for _ in range(100):
        r, c = policy.choose(regions, result(), [])
        policy.update(r.id, c, 10 if c == "boundary" else 0)
    assert policy.counts["r"]["boundary"] > 80
    assert all(n > 0 for n in policy.counts["r"].values())


def test_llm_cache_budget_and_replay(tmp_path):
    client = CachedLLM(FakeLLM(), tmp_path / "cache", tmp_path / "ledger.json", "fake", 1, 2, 1, 1)
    first = client.complete("a")
    second = client.complete("a")
    assert not first.cached and second.cached and first.text == second.text
    assert client.cost == pytest.approx(first.cost_usd * 2)
    with pytest.raises(BudgetExceeded):
        client.complete("third")
    replay = CachedLLM(
        FakeLLM(), tmp_path / "cache", tmp_path / "new.json", "fake", 1, 2, 1, 1, True
    )
    with pytest.raises(RuntimeError, match="cache miss"):
        replay.complete("unknown")


def test_preflight_budget_no_api_call(tmp_path):
    class NeverCall:
        def complete(self, *args):
            raise AssertionError("must not spend")

    client = CachedLLM(NeverCall(), tmp_path, tmp_path / "ledger.json", "fake", 0, 2, 1, 1)
    with pytest.raises(BudgetExceeded):
        client.complete("a")


def test_failed_request_reservation_survives_restart(tmp_path):
    class BrokenProvider:
        def complete(self, *args):
            raise RuntimeError("connection interrupted")

    args = (BrokenProvider(), tmp_path / "cache", tmp_path / "ledger.json", "fake", 0.004, 10, 1, 1)
    client = CachedLLM(*args)
    with pytest.raises(RuntimeError):
        client.complete("a")
    restarted = CachedLLM(*args)
    restarted.entries = []
    with pytest.raises(BudgetExceeded):
        restarted.complete("a")


def test_fake_contracts():
    executor = FakeExecutor()
    r = executor.run(None, {})
    assert ExecResult.model_validate(r.model_dump()) == r
    assert 0 <= coverage_fraction(r) <= 1


def test_snapshot_does_not_copy_secrets_or_change_target(tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    src.mkdir()
    (src / ".env").write_text("SECRET")
    (src / "code.py").write_text("x = 1")
    before = tree_hash(src)
    snapshot(src, dst)
    assert not (dst / ".env").exists()
    (dst / "code.py").write_text("x = 2")
    assert tree_hash(src) == before


def test_end_to_end_and_resume(tmp_path):
    config = Config(
        repo=ROOT / "examples/toy",
        source_dirs=["toy.py"],
        backend="fake",
        replay_only=False,
        require_tag=False,
        arms=["repo", "one-shot", "guided", "random", "coverup"],
        seeds=[1, 2],
        rounds=2,
        cache=tmp_path / "cache",
        runs=tmp_path / "runs",
    )
    directory = run_experiment(config, "test")
    assert len(list(directory.glob("seed-*/*/complete.json"))) == 10
    assert (directory / "metrics.csv").exists()
    assert "SYNTHETIC" in (directory / "report.md").read_text()
    original = (directory / "seed-1/guided/complete.json").read_bytes()
    run_experiment(config, "test")
    assert (directory / "seed-1/guided/complete.json").read_bytes() == original
    changed = config.model_copy(update={"rounds": 3})
    with pytest.raises(ValueError, match="Resume refused"):
        run_experiment(changed, "test")


def test_heldout_only_after_generation(tmp_path, monkeypatch):
    events = []
    original = FakeExecutor.evaluate

    def evaluate(self, root, generated, mutants, baseline):
        events.append({m.split for m in mutants})
        return original(self, root, generated, mutants, baseline)

    monkeypatch.setattr(FakeExecutor, "evaluate", evaluate)
    config = Config(
        repo=ROOT / "examples/toy",
        source_dirs=["toy.py"],
        backend="fake",
        replay_only=False,
        require_tag=False,
        arms=["guided"],
        seeds=[1],
        rounds=3,
        cache=tmp_path / "cache",
        runs=tmp_path / "runs",
    )
    run_experiment(config)
    assert events[-1] == {"heldout"}
    assert all(e == {"feedback"} for e in events[:-1])


def test_insufficient_evidence_and_paired_seeds():
    assert paired_interval({0: 1}, {1: 0})["n"] == 0
    assert paired_interval({0: 1, 1: 1}, {0: 0, 1: 0})["verdict"] == "supported"

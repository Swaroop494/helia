import json

from contracts.models import ExecResult, LLMResponse
from helia.analysis.triage import make_judge, minimize_module


def test_judge_uses_original_evidence_and_returns_decision():
    class LLM:
        def complete(self, prompt, max_tokens):
            assert "ORIGINAL" in prompt
            return LLMResponse(
                text=json.dumps(
                    {"expectation_wrong": True, "rationale": "Documented lower bound is inclusive"}
                ),
                input_tokens=1,
                output_tokens=1,
                cost_usd=0,
            )

    judge = make_judge(LLM(), "def f(): return 1")
    assert judge("def test_f(): assert f() == 2", [])["expectation_wrong"] is True


def test_minimizer_retains_reproduction_and_removes_unrelated_test():
    failure = ExecResult(
        target="original",
        outcome="assert_fail",
        duration_s=0,
        failures=[{"type": "AssertionError", "message": "expected two"}],
    )

    class Executor:
        def run(self, root, generated):
            return (
                failure
                if "test_bug" in next(iter(generated.values()))
                else ExecResult(target="original", outcome="pass", duration_s=0)
            )

    source = "def test_unrelated():\n assert 1 == 1\ndef test_bug():\n assert 1 == 2\n"
    reduced, evidence = minimize_module(source, "test_new.py", None, Executor(), [failure] * 3)
    assert "test_unrelated" not in reduced and "test_bug" in reduced
    assert evidence == [failure] * 3

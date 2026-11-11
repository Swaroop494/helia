import pytest

from helia.fakes import FakeLLM
from helia.llm import AnthropicProvider, BudgetExceeded, CachedLLM


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

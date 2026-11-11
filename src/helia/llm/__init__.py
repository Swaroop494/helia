"""Cached LLM calls with preflight cost reservations and auditable usage."""

import json
import os
import threading
from pathlib import Path
from typing import Protocol

from contracts.models import LLMResponse
from helia.io import digest, native_path, write_json


class BudgetExceeded(RuntimeError):
    """The next call cannot fit inside the configured budget."""


class Provider(Protocol):
    def complete(self, model: str, prompt: str, settings: dict) -> LLMResponse: ...


class AnthropicProvider:
    def __init__(self, live: bool = False):
        self.live = live

    def complete(self, model, prompt, settings):
        if not self.live or not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("Paid requests require --live and ANTHROPIC_API_KEY")
        import anthropic

        client = anthropic.Anthropic(max_retries=0, timeout=60)
        response = client.messages.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=settings["max_tokens"],
            temperature=settings["temperature"],
        )
        return LLMResponse(
            text="\n".join(b.text for b in response.content if b.type == "text"),
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cost_usd=0,
        )


class CachedLLM:
    def __init__(
        self,
        provider: Provider,
        cache: Path,
        ledger: Path,
        model: str,
        budget_usd: float,
        max_calls: int,
        input_per_million: float,
        output_per_million: float,
        replay_only: bool = False,
        run_spend_path: Path | None = None,
        run_budget_usd: float | None = None,
    ):
        self.provider, self.cache, self.ledger, self.model = provider, cache, ledger, model
        self.budget, self.max_calls = budget_usd, max_calls
        self.input_rate, self.output_rate = input_per_million, output_per_million
        self.replay_only = replay_only
        self.run_spend_path = run_spend_path
        self.run_budget = budget_usd if run_budget_usd is None else run_budget_usd
        self.lock = threading.Lock()
        self.entries = json.loads(ledger.read_text()) if ledger.exists() else []
        self.spend_path = ledger.with_name("api-spend.json")
        self.spend = json.loads(self.spend_path.read_text()) if self.spend_path.exists() else []

    @property
    def cost(self):
        return sum(e["cost_usd"] for e in self.entries)

    def complete(self, prompt: str, max_tokens: int = 2048, temperature: float = 0) -> LLMResponse:
        settings = {"max_tokens": max_tokens, "temperature": temperature}
        key = digest(
            {
                "model": self.model,
                "prompt": prompt,
                "settings": settings,
                "provider": type(self.provider).__name__,
            }
        )
        path = native_path(self.cache / (key + ".json"))
        with self.lock:
            if len(self.entries) >= self.max_calls:
                raise BudgetExceeded("Call budget exhausted")
            # UTF-8 bytes upper-bound input tokens; reserve output limit before spending.
            reserve = (
                (len(prompt.encode()) + 1024) * self.input_rate + max_tokens * self.output_rate
            ) / 1e6
            if path.exists():
                response = LLMResponse.model_validate_json(path.read_text())
                response = response.model_copy(update={"cached": True})
                charge = response.cost_usd
            else:
                if self.replay_only:
                    raise RuntimeError(f"Replay cache miss: {key}")
                if (
                    self.cost + reserve > self.budget
                    or sum(e["cost_usd"] for e in self.spend) + reserve > self.budget
                ):
                    raise BudgetExceeded("Insufficient budget for worst-case next call")
                run_spend = []
                if self.run_spend_path is not None:
                    if self.run_spend_path.exists():
                        run_spend = json.loads(self.run_spend_path.read_text())
                    if sum(e["cost_usd"] for e in run_spend) + reserve > self.run_budget:
                        raise BudgetExceeded("Run-wide spend cap exhausted")
                write_json(
                    self.cache / (key + ".request.json"),
                    {
                        "model": self.model,
                        "prompt": prompt,
                        "settings": settings,
                        "input_per_million": self.input_rate,
                        "output_per_million": self.output_rate,
                    },
                )
                # Persist the reservation before a network request. An interrupted request
                # remains charged conservatively, preventing a resume from overspending.
                self.entries.append({"cache_key": key, "cost_usd": reserve, "state": "reserved"})
                write_json(self.ledger, self.entries)
                self.spend.append({"cache_key": key, "cost_usd": reserve, "state": "reserved"})
                write_json(self.spend_path, self.spend)
                run_spend.append({"cache_key": key, "cost_usd": reserve, "state": "reserved"})
                if self.run_spend_path is not None:
                    write_json(self.run_spend_path, run_spend)
                response = self.provider.complete(self.model, prompt, settings)
                charge = (
                    response.input_tokens * self.input_rate
                    + response.output_tokens * self.output_rate
                ) / 1e6
                response = response.model_copy(update={"cost_usd": charge, "cache_key": key})
                write_json(path, response)
                self.spend[-1] = {"cache_key": key, "cost_usd": charge, "state": "complete"}
                write_json(self.spend_path, self.spend)
                run_spend[-1] = {"cache_key": key, "cost_usd": charge, "state": "complete"}
                if self.run_spend_path is not None:
                    write_json(self.run_spend_path, run_spend)
                self.entries.pop()
            if self.cost + charge > self.budget:
                raise BudgetExceeded("Cached call exceeds remaining logical experiment budget")
            self.entries.append(
                {
                    "cache_key": key,
                    "cost_usd": charge,
                    "cached": response.cached,
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "state": "complete",
                }
            )
            write_json(self.ledger, self.entries)
            return response

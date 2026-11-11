"""Configuration-only planning estimates; never execute code or call a provider."""

import math


def estimate(config) -> dict:
    generators = sum(arm in {"guided", "one-shot", "random"} for arm in config.arms)
    runs = len(config.seeds) * len(config.arms)
    calls = generators * len(config.seeds) * min(config.rounds, config.max_calls)
    generation_rounds = generators * len(config.seeds) * config.rounds
    serial_jobs = runs * config.reruns + generation_rounds * config.reruns
    mutant_batches = (runs + generation_rounds) * math.ceil(config.mutant_budget / config.workers)
    return {
        "schema_version": 1,
        "arm_seed_runs": runs,
        "max_generation_calls": calls,
        "api_spend_cap_usd": 0 if config.backend == "fake" or config.replay_only else min(
            config.run_budget_usd, generators * len(config.seeds) * config.budget_usd),
        "planned_test_jobs": serial_jobs + (runs + generation_rounds) * config.mutant_budget,
        "timeout_based_time_s": (serial_jobs + mutant_batches) * config.timeout_s,
        "assumptions": ["Time is a planning estimate, not an upper bound or measured prediction.",
                        "Excludes discovery, container startup, retries, triage and CoverUp.",
                        "All planned generation rounds produce accepted tests; cache hits cost no API spend.",
                        "Paid execution still requires --live and ANTHROPIC_API_KEY."],
    }

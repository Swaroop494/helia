"""Seed-level bootstrap avoids treating correlated mutant outcomes as independent."""

import random
import statistics


def bootstrap(values: list[float], seed: int = 0):
    if len(values) < 2:
        return None
    rng = random.Random(seed)
    means = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(2000))
    return [means[49], means[1949]]


def summarize(finals: list[dict]) -> dict:
    arms = {}
    for arm in sorted({r["arm"] for r in finals}):
        rows = [r for r in finals if r["arm"] == arm]
        scores = [r["heldout_killed"] / r["heldout_total"] for r in rows if r["heldout_total"]]
        kills = sum(r["heldout_killed"] or 0 for r in rows)
        generated = sum(r["generated_tests"] for r in rows)
        arms[arm] = {
            "seeds": len(rows),
            "heldout_score": statistics.mean(scores) if scores else None,
            "heldout_score_ci95": bootstrap(scores),
            "valid_test_rate": sum(r["valid_tests"] for r in rows) / generated if generated else None,
            "cost_per_killed_mutant": sum(r["cost_usd"] for r in rows) / kills if kills else None,
        }
    return {"schema_version": 1, "bootstrap_unit": "seed", "bootstrap_resamples": 2000,
            "bootstrap_seed": 0, "arms": arms}

"""M7: CoverUp artifacts enter the same validation and evaluation path as other arms."""

import json
from pathlib import Path

from pydantic import Field

from contracts.models import Record


class CoverUpBundle(Record):
    target_hash: str
    seed: int
    model: str
    version: str
    cost_usd: float = Field(ge=0)
    calls: int = Field(ge=0)
    tests: dict[str, str]


def load_coverup(
    path: Path, target_hash: str, seed: int, model: str, budget_usd: float, max_calls: int
) -> CoverUpBundle:
    """Import an independently produced, metered CoverUp run; reject unfair comparisons."""
    bundle = CoverUpBundle.model_validate(json.loads((path / f"seed-{seed}.json").read_text()))
    if (bundle.target_hash, bundle.seed, bundle.model) != (target_hash, seed, model):
        raise ValueError("CoverUp provenance does not match this experiment")
    if bundle.cost_usd > budget_usd or bundle.calls > max_calls:
        raise ValueError("CoverUp exceeded the shared experiment budget")
    return bundle

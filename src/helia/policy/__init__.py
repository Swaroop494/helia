"""M6: region priority with exploration and per-region UCB category bandits."""

import math
import random

CATEGORIES = ["boundary", "type", "state", "exception", "logic"]


class Policy:
    def __init__(
        self,
        seed: int,
        exploration: float = 0.15,
        coverage_weight: float = 1,
        alive_weight: float = 1,
    ):
        self.rng = random.Random(seed)
        self.exploration, self.coverage_weight, self.alive_weight = (
            exploration,
            coverage_weight,
            alive_weight,
        )
        self.counts: dict[str, dict[str, int]] = {}
        self.rewards: dict[str, dict[str, float]] = {}
        self.history: list[dict] = []

    def choose(self, regions, baseline, alive, random_arm=False):
        if not regions:
            raise ValueError("No testable regions")
        priorities = {}
        for r in regions:
            executable = [
                line for line in baseline.statements.get(r.file, []) if r.line <= line <= r.end_line
            ]
            uncovered = sum(
                not baseline.contexts.get(r.file, {}).get(str(line)) for line in executable
            )
            priorities[r.id] = self.coverage_weight * uncovered + self.alive_weight * sum(
                m.region == r.id for m in alive
            )
        if random_arm or self.rng.random() < self.exploration:
            region = self.rng.choice(regions)
        else:
            best = max(priorities.values())
            region = self.rng.choice([r for r in regions if priorities[r.id] == best])
        counts = self.counts.setdefault(region.id, dict.fromkeys(CATEGORIES, 0))
        rewards = self.rewards.setdefault(region.id, dict.fromkeys(CATEGORIES, 0.0))
        untried = [c for c in CATEGORIES if not counts[c]]
        if random_arm:
            category = self.rng.choice(CATEGORIES)
        elif untried:
            category = self.rng.choice(untried)
        else:
            category = max(
                CATEGORIES,
                key=lambda c: (
                    rewards[c] / counts[c]
                    + math.sqrt(2 * math.log(sum(counts.values())) / counts[c])
                ),
            )
        self.history.append({"region": region.id, "category": category, "priorities": priorities})
        return region, category

    def update(self, region: str, category: str, reward: float):
        if not math.isfinite(reward):
            raise ValueError("Reward must be finite")
        self.counts[region][category] += 1
        self.rewards[region][category] += reward
        self.history[-1]["reward"] = reward

    def export(self):
        return {"counts": self.counts, "rewards": self.rewards, "history": self.history}

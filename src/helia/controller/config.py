"""Strict experiment configuration; all relative paths resolve against the YAML file."""

from pathlib import Path, PurePosixPath
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from contracts.models import Arm


def default_arms() -> list[Arm]:
    return ["repo", "one-shot", "guided", "coverup"]


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    schema_version: Literal[2] = 2
    repo: Path
    source_dirs: list[str] = Field(default_factory=lambda: ["src"])
    tests: list[str] = Field(default_factory=lambda: ["tests"])
    image: str = "helia-runner:local"
    arms: list[Arm] = Field(default_factory=default_arms)
    seeds: list[int] = Field(default_factory=lambda: list(range(10)))
    rounds: int = Field(default=10, ge=1)
    mutant_budget: int = Field(default=100, ge=2)
    per_file: int = Field(default=25, ge=1)
    heldout_fraction: float = Field(default=0.3, gt=0, lt=1)
    timeout_s: float = Field(default=60, gt=0)
    workers: int = Field(default=2, ge=1, le=32)
    reruns: int = Field(default=3, ge=2)
    max_calls: int = Field(default=10, ge=1)
    max_tokens: int = Field(default=2048, ge=128)
    budget_usd: float = Field(default=5, ge=0)
    run_budget_usd: float = Field(default=5, ge=0)
    model: str = ""
    input_per_million: float = Field(default=0, ge=0)
    output_per_million: float = Field(default=0, ge=0)
    replay_only: bool = True
    backend: Literal["docker", "fake"] = "docker"
    cache: Path = Path(".helia-cache")
    runs: Path = Path("runs")
    exploration: float = Field(default=0.15, ge=0, le=1)
    coverage_weight: float = Field(default=1, ge=0)
    alive_weight: float = Field(default=1, ge=0)
    reward_kills: float = Field(default=1, ge=0)
    reward_coverage: float = Field(default=1, ge=0)
    reward_failures: float = Field(default=0.1, ge=0)
    reward_cost: float = Field(default=0.1, ge=0)
    coverup_bundle: Path | None = None
    require_tag: bool = True
    triage_judge: bool = False
    minimize_leads: bool = True

    @field_validator("source_dirs", "tests")
    @classmethod
    def safe_paths(cls, values):
        for value in values:
            path = PurePosixPath(value.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts or ":" in value or value.startswith("-"):
                raise ValueError("Use relative repository paths, not command options")
        return values

    @model_validator(mode="after")
    def valid_experiment(self):
        if len(set(self.arms)) != len(self.arms) or len(set(self.seeds)) != len(self.seeds):
            raise ValueError("Duplicate arms or seeds")
        if not self.arms or not self.seeds:
            raise ValueError("At least one arm and seed are required")
        if self.backend == "docker" and any(
            a in self.arms for a in ["guided", "one-shot", "random"]
        ):
            if not self.model or self.input_per_million <= 0 or self.output_per_million <= 0:
                raise ValueError("Configure an explicit model and current token prices")
        if "coverup" in self.arms and self.backend != "fake" and not self.coverup_bundle:
            raise ValueError("CoverUp arm requires a provenance and cost-accounted coverup_bundle")
        return self


def load_config(path: Path) -> Config:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    config = Config.model_validate(raw)
    for field in ["repo", "cache", "runs", "coverup_bundle"]:
        value = getattr(config, field)
        if value is not None:
            setattr(config, field, (path.parent / value).resolve())
    if not config.repo.is_dir():
        raise ValueError(f"Repository does not exist: {config.repo}")
    return config

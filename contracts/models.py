"""Version 1 records. Unknown fields are rejected to detect producer drift."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Category = Literal["boundary", "type", "state", "exception", "logic"]
Outcome = Literal["pass", "assert_fail", "exception", "timeout", "infra_error", "no_tests"]
Arm = Literal["repo", "one-shot", "guided", "random", "coverup"]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1


class Region(Record):
    id: str
    file: str
    name: str
    line: int
    end_line: int
    source: str
    calls: list[str] = Field(default_factory=list)


class RepoIndex(Record):
    regions: list[Region]
    files: list[str]
    fixtures: dict[str, str] = Field(default_factory=dict)
    tests: dict[str, str] = Field(default_factory=dict)
    parse_errors: dict[str, str] = Field(default_factory=dict)


class Mutant(Record):
    id: str
    file: str
    line: int = Field(ge=1)
    operator: str
    occurrence: int = Field(ge=0)
    region: str
    split: Literal["feedback", "heldout"] = "feedback"
    operator_args: dict = Field(default_factory=dict)

    @field_validator("file")
    @classmethod
    def relative_file(cls, value: str) -> str:
        from pathlib import PurePosixPath

        path = PurePosixPath(value.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts or ":" in value:
            raise ValueError("mutant file must be repository-relative")
        return path.as_posix()


class ExecResult(Record):
    test_id: str = "suite"
    target: Literal["original", "mutant"]
    mutant_id: str | None = None
    outcome: Outcome
    duration_s: float = Field(ge=0)
    output: str = ""
    failures: list[dict] = Field(default_factory=list)
    contexts: dict[str, dict[str, list[str]]] = Field(default_factory=dict)
    statements: dict[str, list[int]] = Field(default_factory=dict)
    test_outcomes: dict[str, str] = Field(default_factory=dict)


class Failure(Record):
    signature: str
    category: Category
    region: str
    mutant_id: str
    test_id: str
    summary: str


class BugLead(Record):
    id: str
    status: Literal["invalid", "flaky", "bug_lead", "confirmed", "infrastructure"]
    test_source: str
    evidence: list[ExecResult]
    rationale: str


class LLMResponse(Record):
    text: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost_usd: float = Field(ge=0)
    cache_key: str = ""
    cached: bool = False


class Metrics(Record):
    arm: Arm
    seed: int
    round: int
    feedback_killed: int
    feedback_total: int
    heldout_killed: int | None = None
    heldout_total: int | None = None
    coverage: float
    valid_tests: int
    generated_tests: int
    unique_failures: int
    cost_usd: float
    duration_s: float
    bug_leads: int = 0
    confirmed_bugs: int = 0
    valid_test_rate: float | None = None
    heldout_score: float | None = None
    cost_per_heldout_kill: float | None = None
    coverage_gain: float = 0
    new_failure_signatures: int = 0
    feedback_infrastructure_errors: int = 0
    feedback_timeouts: int = 0
    heldout_infrastructure_errors: int | None = None
    heldout_timeouts: int | None = None

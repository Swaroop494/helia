"""M4 and M9: conservative kill semantics, failure dedupe, original-code triage."""

import re
from typing import Literal, cast

from contracts.models import BugLead, Category, Failure
from helia.io import digest


def killed(result) -> bool:
    """Timeout, collection errors and infrastructure failures never count as kills."""
    return result.outcome in {"assert_fail", "exception"} and any(
        f.get("phase") == "call" for f in result.failures
    )


def category_for(text: str) -> Category:
    lower = text.lower()
    for category, terms in {
        "type": ["typeerror", "attributeerror"],
        "boundary": ["indexerror", "overflow", "empty", "boundary"],
        "state": ["state", "cache", "keyerror"],
        "exception": ["raises", "exception", "valueerror"],
    }.items():
        if any(term in lower for term in terms):
            return cast(Category, category)
    return "logic"


def analyse(results, mutants):
    by_id = {m.id: m for m in mutants}
    records = {}
    for result in results:
        mutant = by_id[result.mutant_id]
        if mutant.split != "feedback":
            raise ValueError("Held-out results cannot enter the learning analyser")
        if not killed(result):
            continue
        for failure in result.failures:
            summary = failure.get("type", "Exception")
            # Never pass traceback/source/assertion rewrites from a mutant to the LLM.
            normalized = re.sub(r"0x[0-9a-f]+|\b\d+\b", "#", failure.get("message", ""))
            signature = digest([mutant.region, summary, normalized])[:24]
            records[signature] = Failure(
                signature=signature,
                category=category_for(summary),
                region=mutant.region,
                mutant_id=mutant.id,
                test_id=failure.get("nodeid", "suite"),
                summary=f"{summary} in a test of this region; inspect original semantics.",
            )
    return list(records.values())


def coverage_fraction(result) -> float:
    total = sum(len(lines) for lines in result.statements.values())
    covered = sum(
        sum(bool(result.contexts.get(file, {}).get(str(line))) for line in lines)
        for file, lines in result.statements.items()
    )
    return covered / total if total else 0.0


def triage(source: str, evidence: list, judge=None) -> BugLead:
    status: Literal["invalid", "flaky", "bug_lead", "confirmed", "infrastructure"]
    outcomes = {r.outcome for r in evidence}
    if outcomes & {"infra_error", "timeout", "no_tests"}:
        status, rationale = "infrastructure", "Execution did not produce reliable test evidence."
    elif len(outcomes) > 1 or len({digest(r.failures) for r in evidence}) > 1:
        status, rationale = "flaky", "Repeated original runs disagree."
    elif outcomes == {"pass"}:
        status, rationale = "invalid", "No reproducible failure on original code."
    elif judge:
        decision = judge(source, evidence)
        status = "invalid" if decision.get("expectation_wrong") is True else "bug_lead"
        rationale = decision.get("rationale", "Requires human review.")
    else:
        status, rationale = "bug_lead", "Reproducible failure; expectation needs human review."
    return BugLead(
        id=digest(source)[:24],
        status=status,
        test_source=source,
        evidence=evidence,
        rationale=rationale,
    )

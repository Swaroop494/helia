"""M8: reproducible arm orchestration and resumable seed-level experiments."""

import json
import subprocess
import time
from pathlib import Path

from contracts.models import BugLead, Failure, Metrics
from helia.analysis import analyse, coverage_fraction, killed, triage
from helia.baselines import load_coverup
from helia.controller.config import Config
from helia.executor import DockerExecutor
from helia.fakes import FakeExecutor, FakeLLM
from helia.generator import build_prompt, validate_response
from helia.io import digest, tree_hash, write_json
from helia.llm import AnthropicProvider, BudgetExceeded, CachedLLM
from helia.mutants import sample
from helia.policy import Policy
from helia.repo_index import build_index


def git_metadata(root: Path):
    def git(*args):
        p = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
        return p.stdout.strip() if p.returncode == 0 else None

    return {
        "commit": git("rev-parse", "HEAD"),
        "tag": git("describe", "--exact-match", "--tags", "HEAD"),
        "dirty": bool(git("status", "--porcelain")),
    }


def run_experiment(config: Config, run_id: str | None = None) -> Path:
    """Resume completed arms and replay incomplete arms from cached calls."""
    started = time.monotonic()
    target_hash = tree_hash(config.repo)
    tool_root = Path(__file__).resolve().parents[3]
    implementation_hash = digest(
        [
            tree_hash(tool_root / "src"),
            tree_hash(tool_root / "contracts"),
            (tool_root / "uv.lock").read_text(),
        ]
    )
    identity = digest(
        {
            "config": config.model_dump(mode="json"),
            "target_hash": target_hash,
            "implementation_hash": implementation_hash,
        }
    )
    run_id = run_id or identity[:16]
    if Path(run_id).name != run_id or run_id in {".", ".."}:
        raise ValueError("run_id must be a single directory name")
    run_dir = config.runs / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    lock = run_dir / ".lock"
    try:
        fd = lock.open("x")
    except FileExistsError:
        raise RuntimeError(
            f"Run is locked: {lock}. Remove only after verifying no controller is running."
        ) from None
    try:
        fd.write(str(__import__("os").getpid()))
        fd.close()
        manifest_path = run_dir / "manifest.json"
        if manifest_path.exists() and json.loads(manifest_path.read_text())["identity"] != identity:
            raise ValueError("Resume refused: configuration or target contents changed")
        metadata = git_metadata(config.repo)
        tool_metadata = git_metadata(Path(__file__).resolve().parents[3])
        if (
            config.require_tag
            and config.backend != "fake"
            and (
                not tool_metadata["tag"]
                or tool_metadata["dirty"]
                or not metadata["commit"]
                or metadata["dirty"]
            )
        ):
            raise ValueError(
                "Experiments require a clean tagged Helia checkout and clean pinned target"
            )
        previous_manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
        write_json(
            manifest_path,
            {
                **previous_manifest,
                "identity": identity,
                "config": config.model_dump(mode="json"),
                "target_hash": target_hash,
                "target_git": metadata,
                "helia_git": tool_metadata,
                "implementation_hash": implementation_hash,
                "synthetic": config.backend == "fake",
                "status": "running",
            },
        )
        executor = (
            FakeExecutor()
            if config.backend == "fake"
            else DockerExecutor(
                config.image, config.source_dirs, config.tests, config.timeout_s, config.workers
            )
        )
        image_id = getattr(executor, "image", "synthetic")
        if previous_manifest.get("image_id", image_id) != image_id:
            raise ValueError("Resume refused: runner image changed")
        manifest = json.loads(manifest_path.read_text())
        manifest["image_id"] = image_id
        write_json(manifest_path, manifest)
        index = build_index(config.repo, config.source_dirs)
        if not index.regions or index.parse_errors:
            raise ValueError(f"Repository index is empty or has parse errors: {index.parse_errors}")
        write_json(run_dir / "index.json", index)
        all_mutants = executor.discover(config.repo, index)
        for seed in config.seeds:
            mutants = sample(
                all_mutants, seed, config.mutant_budget, config.per_file, config.heldout_fraction
            )
            if len(mutants) < 2:
                raise ValueError("At least two mutants are required for an honest held-out split")
            write_json(run_dir / f"seed-{seed}/mutants.json", [m.model_dump() for m in mutants])
            for arm in config.arms:
                arm_dir = run_dir / f"seed-{seed}" / arm
                if (arm_dir / "complete.json").exists():
                    continue
                _run_arm(config, index, mutants, executor, arm, seed, arm_dir, target_hash)
        manifest = json.loads(manifest_path.read_text())
        if tree_hash(config.repo) != target_hash:
            raise RuntimeError("Target changed during execution; results cannot be marked complete")
        manifest.update(status="complete", duration_s=time.monotonic() - started)
        write_json(manifest_path, manifest)
        from helia.controller.report import report

        report(run_dir)
        return run_dir
    except Exception as exc:
        write_json(run_dir / "error.json", {"type": type(exc).__name__, "message": str(exc)})
        raise
    finally:
        lock.unlink(missing_ok=True)


def _run_arm(config, index, mutants, executor, arm, seed, directory, target_hash):
    directory.mkdir(parents=True, exist_ok=True)
    # Keep a persistent spend ledger across restarts. Replaying completed requests
    # uses a fresh logical ledger but the cached provider is free of new API charges.
    ledger = directory / "llm-ledger.json"
    llm = CachedLLM(
        FakeLLM() if config.backend == "fake" else AnthropicProvider(),
        config.cache,
        ledger,
        config.model or "fake",
        config.budget_usd,
        config.max_calls,
        config.input_per_million,
        config.output_per_million,
        config.replay_only,
    )
    if ledger.exists():
        # Preserve spent/reserved amounts; reconstruct deterministic algorithmic calls
        # through a separate replay ledger and subtract unresolved reservations.
        llm.entries = []
    policy = Policy(seed, config.exploration, config.coverage_weight, config.alive_weight)
    feedback = [m for m in mutants if m.split == "feedback"]
    heldout = [m for m in mutants if m.split == "heldout"]
    generated: dict[str, str] = {}
    seen: set[str] = set()
    failures: dict[str, Failure] = {}
    leads: list[BugLead] = []
    metrics: list[dict] = []
    count = valid = 0
    started = time.monotonic()
    originals = [executor.run(config.repo, {}) for _ in range(config.reruns)]
    if any(r.outcome != "pass" for r in originals):
        write_json(directory / "original-failures.json", [r.model_dump() for r in originals])
        raise RuntimeError("Original repository suite must pass repeatedly before evaluation")
    baseline = originals[0]
    results = executor.evaluate(config.repo, generated, feedback, baseline)
    kills = {r.mutant_id for r in results if killed(r)}
    external_cost = 0.0

    def record(round_number, held_results=None):
        held_kills = sum(killed(r) for r in held_results) if held_results is not None else None
        cost = llm.cost + external_cost
        metric = Metrics(
            arm=arm,
            seed=seed,
            round=round_number,
            feedback_killed=len(kills),
            feedback_total=len(feedback),
            heldout_killed=held_kills,
            heldout_total=len(heldout) if held_results is not None else None,
            coverage=coverage_fraction(baseline),
            valid_tests=valid,
            generated_tests=count,
            unique_failures=len(failures),
            cost_usd=cost,
            duration_s=time.monotonic() - started,
            bug_leads=sum(b.status == "bug_lead" for b in leads),
            valid_test_rate=valid / count if count else None,
            heldout_score=held_kills / len(heldout) if held_kills is not None and heldout else None,
            cost_per_heldout_kill=cost / held_kills if held_kills else None,
            coverage_gain=coverage_fraction(baseline) - coverage_fraction(originals[0]),
            new_failure_signatures=len(failures)
            - (metrics[-1]["unique_failures"] if metrics else 0),
            feedback_infrastructure_errors=sum(r.outcome == "infra_error" for r in results),
            feedback_timeouts=sum(r.outcome == "timeout" for r in results),
            heldout_infrastructure_errors=sum(r.outcome == "infra_error" for r in held_results)
            if held_results is not None
            else None,
            heldout_timeouts=sum(r.outcome == "timeout" for r in held_results)
            if held_results is not None
            else None,
        )
        metrics.append(metric.model_dump())
        write_json(directory / "metrics.json", metrics)

    record(0)
    imported = []
    if arm == "coverup":
        if config.backend == "fake":
            imported = [FakeLLM().complete("fake", "coverup", {}).text]
        else:
            bundle = load_coverup(
                config.coverup_bundle,
                target_hash,
                seed,
                config.model,
                config.budget_usd,
                config.max_calls,
            )
            imported, external_cost = list(bundle.tests.values()), bundle.cost_usd
    rounds = 0 if arm == "repo" else (len(imported) if arm == "coverup" else config.rounds)
    for round_number in range(1, rounds + 1):
        previous_kills, previous_coverage, previous_failures, previous_cost = (
            len(kills),
            coverage_fraction(baseline),
            len(failures),
            llm.cost,
        )
        # One-shot means independent prompts with no mutation feedback, under the
        # same total call/token budget as the iterative arm.
        region, category = policy.choose(
            index.regions,
            originals[0] if arm == "one-shot" else baseline,
            [] if arm == "one-shot" else [m for m in feedback if m.id not in kills],
            random_arm=arm in {"random", "one-shot"},
        )
        try:
            if arm == "coverup":
                response = imported[round_number - 1]
            else:
                prompt = build_prompt(
                    index,
                    region,
                    category,
                    [f.model_dump() for f in failures.values()] if arm == "guided" else [],
                )
                response = llm.complete(prompt, max_tokens=config.max_tokens).text
            source, key, num_tests = validate_response(response, seen)
            count += num_tests
            seen.add(key)
            name = f"tests/test_helia_{key[:16]}.py"
            candidate = {**generated, name: source}
            evidence = [executor.run(config.repo, candidate) for _ in range(config.reruns)]
            if all(
                r.outcome == "pass"
                and any(node.startswith(name + "::") for node in r.test_outcomes)
                and all(
                    status == "passed"
                    for node, status in r.test_outcomes.items()
                    if node.startswith(name + "::")
                )
                for r in evidence
            ):
                generated, baseline = candidate, evidence[0]
                valid += num_tests
                results = executor.evaluate(config.repo, generated, feedback, baseline)
                kills = {r.mutant_id for r in results if killed(r)}
                for failure in analyse(results, feedback):
                    failures[failure.signature] = failure
                write_json(
                    directory / f"round-{round_number}/results.json",
                    [r.model_dump() for r in results],
                )
            else:
                from helia.analysis.triage import make_judge, minimize_module

                isolated = [executor.run(config.repo, {name: source}) for _ in range(config.reruns)]
                lead_source = source
                if config.minimize_leads:
                    lead_source, isolated = minimize_module(
                        source, name, config.repo, executor, isolated, config.reruns
                    )
                judge = make_judge(llm, region.source) if config.triage_judge else None
                try:
                    lead = triage(lead_source, isolated, judge)
                except (BudgetExceeded, ValueError):
                    lead = triage(lead_source, isolated)
                leads.append(lead)
                write_json(directory / f"triage/{lead.id}.json", lead)
        except BudgetExceeded:
            break
        except (ValueError, SyntaxError) as exc:
            count += 1
            write_json(directory / f"round-{round_number}/rejected.json", {"reason": str(exc)})
        reward = (
            config.reward_kills * (len(kills) - previous_kills)
            + config.reward_coverage * (coverage_fraction(baseline) - previous_coverage)
            + config.reward_failures * (len(failures) - previous_failures)
            - config.reward_cost * (llm.cost - previous_cost)
        )
        policy.update(region.id, category, reward)
        write_json(directory / "policy.json", policy.export())
        write_json(directory / "generated.json", generated)
        record(round_number)
    # Held-out execution happens only after all generation and policy updates finish.
    held_results = executor.evaluate(config.repo, generated, heldout, baseline)
    write_json(directory / "heldout-results.json", [r.model_dump() for r in held_results])
    record(rounds + 1, held_results)
    write_json(
        directory / "complete.json", {"final": metrics[-1], "synthetic": config.backend == "fake"}
    )

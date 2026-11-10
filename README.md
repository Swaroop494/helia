# Helia

Failure-guided pytest generation for whole Python repositories. Helia indexes original
source, samples Cosmic Ray mutants, learns only from a feedback partition, and evaluates
the held-out partition after generation stops. It includes a two-level region/category
policy, cached Anthropic calls, Docker execution, original-code failure triage, baseline
adapters, run provenance, CSV reports and paired hypothesis estimates.

## Quick start

Python 3.12 is the reference environment. Install [uv](https://docs.astral.sh/uv/), then:

```powershell
uv sync --frozen --extra dev
uv run pytest -q
uv run helia doctor
uv run helia run configs/demo.yaml
```

The demo is **synthetic**. It never executes target code or contacts an LLM. Its numbers
validate plumbing and are explicitly excluded from research conclusions. The final
command prints the run directory containing `report.md`, `metrics.csv`, `hypotheses.json`,
policy histories, generated tests, cost ledgers and per-mutant evidence.

On this Windows workspace the environment is already installed. You can also run:

```powershell
.venv\Scripts\helia.exe run configs/demo.yaml
```

## Real execution

1. Install Docker Desktop with WSL2 on Windows, or Docker Engine on Linux.
2. Build the runner: `docker build -f docker/Dockerfile -t helia-runner:local .`
3. Fetch target checkouts: `uv run python scripts/prepare_targets.py`.
4. Audit each target's licence, LOC and dependencies; build a target-specific image when
   dependencies beyond the runner lock are required. Install dependencies at image-build
   time only. Use hash-pinned requirements and record the resulting image ID.
5. Copy `configs/experiment.yaml` for each target. Set source/test paths, image, an explicit
   Anthropic model and its current input/output prices. Set `ANTHROPIC_API_KEY` in the
   controller environment and `replay_only: false` for a paid run. API keys are never sent
   to the test container. `replay_only: true` refuses missing cache entries.
6. Supply a metered CoverUp bundle (below), or remove that arm while preparing the others.
7. Commit and tag the reviewed implementation and use clean, pinned target checkouts.
   Research configurations require these provenance checks. For local development only,
   set `require_tag: false`.
8. Run `uv run helia run configs/experiment.yaml`. Ten seeds are configured by default.

Every job uses a disposable non-root, network-off Docker container with a read-only root,
dropped capabilities, no Docker socket, memory/CPU/PID limits and timeouts. Only a copied
repository and disposable output directory are mounted. Pool slots limit concurrency;
containers are replaced after each job to prevent cross-job pollution. There is no unsafe
host-execution fallback. Docker isolates ordinary untrusted tests; hostile kernel exploits
require stronger isolation such as a dedicated VM.

## Arms and budget fairness

- `repo`: existing suite, no generation cost.
- `one-shot`: independent prompts without failure feedback, sharing the same total call
  and token budget as the guided arm. Multiple independent prompts are allowed; there is
  no repair loop or feedback from earlier generated tests in its prompts.
- `guided`: uncovered-line/alive-mutant region priority, epsilon exploration, per-region
  UCB category policy and rewards for new kills, coverage and failure signatures minus cost.
- `random`: the same loop and budget with random choices, for the H4 ablation.
- `coverup`: imports tests from an independently run CoverUp experiment, checks its model,
  target fingerprint, seed and metered budget, then uses Helia's shared validator/executor.

The CoverUp adapter currently **imports** results; it does not launch a network-connected
CoverUp process or enforce that external process's spending. Run CoverUp in its own
controlled environment with a provider spend limit. Each `coverup_bundle/seed-N.json` is:

```json
{
  "schema_version": 1,
  "target_hash": "fingerprint from this target's manifest",
  "seed": 0,
  "model": "the same configured model",
  "version": "the installed CoverUp version",
  "cost_usd": 0.50,
  "calls": 3,
  "tests": {"test_coverup_1.py": "def test_example():\n    assert True\n"}
}
```

The example demonstrates the record shape, not a meaningful test. Do not report H5 from
unmetered external runs. CoverUp CLI integration details are documented in its
[upstream README](https://github.com/plasma-umass/coverup).

Cache keys include provider, model, prompt and generation settings. Cached responses
consume the same *logical* budget as their original calls, so replay cannot improve an
arm's budget. Separate API spend reservations survive interruptions. Ambiguous failed
requests retain their worst-case reservation rather than silently allowing overspending.
Configured prices must match the provider; Helia cannot enforce provider-side account limits.

## Commands

```text
helia doctor
helia index CONFIG
helia run CONFIG [--run-id NAME]
helia report RUN_DIRECTORY
helia plot RUN_DIRECTORY
helia schemas [OUTPUT_DIRECTORY]
helia sensitivity CONFIG --exploration 0 0.15 0.3 --kill-weight 0.5 1 2
helia verify-fix CONFIG FIX_COMMIT GENERATED_JSON --output evidence.json
```

Install plots with `uv sync --extra dev --extra plots`. `verify-fix` requires a clean target
checked out at the fix commit, passes on that version and failures after reverse-applying
the Python patch to a disposable snapshot. It never reverts your working tree. Mixed
code/test or dependency fixes need manual curation. Confirmation is restricted to stable
call-phase failures; timeouts and infrastructure errors do not count.

## Reproducibility and resume

Run IDs default to a hash of the configuration and target contents. Reusing an ID with
changed input is rejected. Completed arms are preserved; an interrupted arm is replayed
from the beginning using cached LLM responses. The `.lock` prevents two controllers from
writing the same run. If a process is killed, remove a stale lock only after verifying that
the old process stopped. Do not modify the target or cache during a run.

Only a passing original suite can be scored. Generated modules must collect and pass
repeatedly; skipped/xfail-only modules are rejected. Unknown coverage runs the full suite;
known uncovered lines are recorded as untested, not kills. Collection failures, timeout,
infrastructure failure and invalid mutations never count as kills. Stable original failures
are unconfirmed bug leads unless historical ground truth or human review confirms them.

## Implementation status

The repository contains all nine module boundaries and working core paths, strict versioned
contracts, a real Cosmic Ray adapter, local unit/contract tests, synthetic end-to-end tests,
Linux Docker integration CI, a dev container, target pins, experiment configurations and
reporting. See `docs/implementation-status.md` for the remaining work and verification limits.

This is not a completed ten-week research campaign. Linux CI verifies Docker execution,
target suite qualification and one curated historical Toolz bug. Paid generation,
external CoverUp generation and the 3-repository / 10-seed experiments require the
specified model, spend cap, credentials and metered baseline inputs.
No experimental superiority or confirmed real-world bug is claimed by the demo.

## Development

```text
uv run ruff check .
uv run mypy src contracts
uv run pytest -q
uv run helia schemas
```

`uv.lock` is the single resolved dependency source. `requirements.lock` is its hash-pinned
Docker export: regenerate with `uv export --frozen --no-dev --no-emit-project -o requirements.lock`.
CI does not make real LLM calls. Set `HELIA_DOCKER_IMAGE` to enable the sandbox smoke test.

## References

- [Cosmic Ray mutation API](https://cosmic-ray.readthedocs.io/en/latest/reference/api/cosmic_ray.html)
- [Coverage dynamic contexts](https://coverage.readthedocs.io/en/latest/contexts.html)
- [CoverUp](https://github.com/plasma-umass/coverup)


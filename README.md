# Helia

Helia is a research prototype for generating pytest tests across Python repositories. It uses mutation testing and test feedback to guide generation, then measures performance on a held-out set of mutants.

The project provides a reproducible experiment pipeline with Docker-based execution, budgeted and cached LLM requests, baseline arms, failure triage, resumable runs, and machine-readable and human-readable reports. The synthetic demo exercises the pipeline without running target code or making API requests. It is a smoke test, not research evidence.

## How an experiment works

1. Helia statically indexes Python source and existing tests.
2. Cosmic Ray creates candidate mutants. Helia samples them deterministically and divides them into feedback and held-out groups.
3. A baseline run measures the existing suite. A run cannot be scored if the original suite does not pass repeatedly.
4. Generation arms propose tests. Helia validates and reruns generated modules, then uses feedback mutants and coverage to guide the policy.
5. After generation ends, Helia evaluates the held-out mutants and writes evidence, metrics, and reports.

Held-out outcomes do not feed back into generation. Timeouts, collection errors, infrastructure errors, invalid mutants, and tests without relevant coverage are not counted as kills.

## Quick start

Python 3.12 is the reference environment. Install [uv](https://docs.astral.sh/uv/), then run:

```sh
uv sync --frozen --extra dev
uv run pytest -q
uv run helia doctor
uv run helia run configs/demo.yaml
```

The demo uses the fake executor and fake LLM. It makes no network calls and executes no target code. Its report is marked synthetic and must not be used as evidence for the research hypotheses. The command prints the run directory. Results include a Markdown report, an HTML report, SVG learning curves, CSV metrics, arm summaries, policy history, generated tests, cost ledgers, and per-mutant evidence.

## Experiment arms

| Arm | Purpose |
| --- | --- |
| `repo` | Measures the repository's existing test suite. |
| `one-shot` | Generates independent tests without failure feedback between prompts. |
| `guided` | Selects source regions and test categories using coverage, surviving mutants, exploration, and per-region bandit rewards. |
| `random` | Uses the same generation loop and budget with randomized choices. |
| `coverup` | Imports a separately produced, metered CoverUp bundle and validates its tests through Helia. |

Arms share the experiment settings and comparison pipeline. LLM generation arms have per-arm call, token, and dollar limits. The `run_budget_usd` setting caps total Helia API reservations across arms and seeds within one run. A matrix creates separate run folders, so its aggregate possible spend is the sum of each folder's cap.

## Running with a live provider

Live calls require both `ANTHROPIC_API_KEY` in the controller environment and the explicit `--live` flag. Without `--live`, Helia only replays cache entries. Use `--dry-run` to validate and print configuration without starting Docker or making model calls.

Before an experiment:

1. Install Docker Desktop with WSL2 on Windows, or Docker Engine on Linux.
2. Build the isolated runner image with `docker build -f docker/Dockerfile -t helia-runner:local .`.
3. Prepare pinned targets with `uv run python scripts/prepare_targets.py`.
4. Review target licence, source size, dependencies, and suite behavior.
5. Configure the repository, source and test paths, image, model, token prices, call/token limits, budgets, and seeds.
6. Put the API key in the controller environment and explicitly enable live requests:

```sh
uv run helia run configs/experiment.yaml --live
```

The default `replay_only: true` blocks missing cache entries. To permit cache misses during a live run, set `replay_only: false`. Configure current provider prices accurately. Helia enforces its configured reservations, while provider-side account limits remain controlled by the provider.

Every test job runs in a fresh Docker container with network disabled, non-root identity, a read-only root filesystem, dropped capabilities, and CPU, memory, process, and time limits. Only a repository snapshot and disposable output directory are mounted. Helia has no host-execution fallback. Docker protects against ordinary test code, while hostile kernel exploits require stronger isolation.

## CoverUp bundles

The CoverUp adapter imports results. It does not launch CoverUp. Run CoverUp separately with a provider spend cap, then provide a bundle at `coverup_bundle/seed-N.json`:

```json
{
  "schema_version": 1,
  "target_hash": "target fingerprint from the run manifest",
  "seed": 0,
  "model": "configured model name",
  "version": "installed CoverUp version",
  "cost_usd": 0.50,
  "calls": 3,
  "tests": {
    "test_coverup_1.py": "def test_example():\\n    assert True\\n"
  }
}
```

Helia checks the target fingerprint, seed, model, cost, and call count against the experiment configuration. This validates the supplied record. It cannot independently verify the external producer's API spending. Do not use an unmetered bundle for cost comparisons.

## Commands

```text
helia doctor
helia index CONFIG
helia run CONFIG [--run-id NAME] [--live | --dry-run]
helia experiment CONFIG [CONFIG ...] [--live]
helia estimate CONFIG
helia report RUN_DIRECTORY
helia plot RUN_DIRECTORY
helia bugcheck CONFIG FIX_COMMIT RUN_DIRECTORY [--output evidence.json]
helia verify-fix CONFIG FIX_COMMIT GENERATED_JSON [--output evidence.json]
helia sensitivity CONFIG [--exploration VALUES] [--kill-weight VALUES]
helia schemas [OUTPUT_DIRECTORY]
```

`doctor` checks the Docker engine, key presence, Python dependencies, and free disk space. It does not display the API key. `estimate` computes a configuration-based call, cost-cap, and time estimate without running jobs. Time is approximate and depends on the configured timeout and workload assumptions.

`experiment` expands one or more config files into repository, arm, and seed runs. Completed tuples are preserved on resume. `bugcheck` evaluates saved arm tests against a given historical fix by reverse-applying the patch to a disposable repository snapshot. `verify-fix` performs the same differential check for one generated-test JSON file. Both require a clean target checked out at the fix commit. Historical confirmation requires stable passing evidence on fixed code and stable call-phase failure evidence on reverted code.

`audit_targets.py` collects licence text and source-size evidence, then runs a baseline suite plus three reruns:

```sh
uv run python scripts/audit_targets.py configs/repo-toolz.yaml configs/repo-tabulate.yaml
```

Install the optional plotting dependencies with `uv sync --extra dev --extra plots` before using `helia plot`.

## Configuration and reproducibility

Matrix commands print every tuple result and exit with status 1 if any tuple fails.
Rerun the same command to retry unfinished work. Malformed configuration errors appear
on stderr. Ctrl+C exits with status 130.

Indexing accepts Python source encoding declarations and records invalid files in
`parse_errors`. It rejects repositories above 10,000 Python files, 2 MB per file or
50 MB total source bytes; ignored directories such as `.venv` are pruned first.
Generated modules that overlap accepted top-level tests with identical imports and
helpers are rejected so duplicate tests cannot inflate valid-test counts.

Configurations are strict YAML documents validated by Pydantic. Relative paths resolve from the config file. See [configs/demo.yaml](configs/demo.yaml) for a fake run and [configs/experiment.yaml](configs/experiment.yaml) for the real-run template. Current config contract version is 3. Schema files can be regenerated with `uv run helia schemas`.

Default run IDs derive from configuration and target contents. Manifests record config and implementation hashes, target fingerprint, Git commits, runner image, and whether the run is synthetic. Reusing a run ID with changed inputs is rejected. Completed arms are retained, while interrupted work can resume from cached model responses. Local locks are reclaimed only when Helia verifies the recorded process on the same host has exited. Ambiguous and foreign-host locks need manual investigation.

Do not change the target repository or shared response cache during a run. Cache keys include provider, model, prompt, and generation settings. Cache replays use logical arm budget. Reservations for interrupted paid requests remain charged conservatively.

## Reports and interpretation

Each run exports:

- `report.md` and `report.html` with per-arm comparisons and learning curves.
- `learning-curves.svg` and, when plotting extras are installed, `learning-curves.png`.
- `metrics.csv`, `arm-summary.json`, and `hypotheses.json`.
- Run manifests, event logs, generated tests, policy histories, LLM ledgers, and mutant evidence.

Held-out mutation score is reported with bootstrap intervals across seeds. The summary also includes valid-test rate and cost per killed held-out mutant. Undefined rates and insufficient seed counts remain explicitly unavailable. Intervals across seeds do not establish causality. Interpret policy histories and learning curves directly when assessing learning behavior.

Fake runs are visibly marked synthetic and are excluded from research conclusions. This repository has not completed its full multi-repository, multi-seed campaign or paid generation. Do not claim superiority or confirmed real-world bugs from demo results. See [docs/implementation-status.md](docs/implementation-status.md) for the verification ledger and known limitations.

## Development

```sh
uv sync --frozen --extra dev
uv run ruff check .
uv run mypy src contracts
uv run pytest -q
uv run helia schemas
```

`uv.lock` is the resolved dependency source. The hash-pinned Docker dependency export is `requirements.lock`. Regenerate it with:

```sh
uv export --frozen --no-dev --no-emit-project -o requirements.lock
```

CI runs fake LLM tests. Docker integration tests run when `HELIA_DOCKER_IMAGE` is configured.

## Architecture

The main code paths are organized by responsibility:

```text
CLI and config
  -> controller and policy
  -> repository index and mutant sampler
  -> cached LLM / baseline adapters
  -> Docker executor and pytest worker
  -> analysis, triage, metrics, reports
```

The source packages are under [src/helia](src/helia), versioned data contracts are under [contracts](contracts), and the Docker worker image is defined in [docker](docker). The CI workflow runs linting, type checks, tests, image validation, target qualification, and one curated historical-fix check.

## References

- [Cosmic Ray mutation API](https://cosmic-ray.readthedocs.io/en/latest/reference/api/cosmic_ray.html)
- [Coverage dynamic contexts](https://coverage.readthedocs.io/en/latest/contexts.html)
- [CoverUp](https://github.com/plasma-umass/coverup)

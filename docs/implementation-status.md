# Implementation and verification ledger

## Implemented

- M1: AST files/functions/classes, qualified names, conservative static call relationships,
  fixtures/test examples, parse diagnostics, dynamic per-test coverage and test selection.
- M2: Cosmic Ray sessions, stable mutant identities, caps, seeded file/function sampling,
  fixed feedback/held-out partition and stored metadata.
- M3: bounded parallel Docker slots with fresh containers, pinned dependency export,
  network isolation, non-root user, resource limits, timeouts, structured pytest outcomes.
- M4: conservative kills, failure taxonomy, normalized signatures, feedback-only analysis.
- M5: original-source context, Anthropic client, cache, budget reservations, syntax validation,
  structural module dedupe, repeated suite validation, quarantine and valid-test counts.
- M6: priority/exploration region choice, UCB category bandits, configurable rewards, logs.
- M7: repo, independent one-shot, guided and random arms; provenance-checked CoverUp import.
- M8: strict YAML configs, run stores, resume, seeds, sweeps, metrics CSV, optional plots,
  paired estimates and conservative H1-H5 report sections.
- M9: flaky/invalid/infrastructure/bug-lead triage and historical-fix differential verification.

## Limitations and unfinished scope

- Docker is absent on the implementation host; sandbox integration is defined in Linux CI
  but has not been executed here. Dependency/image builds and cross-platform execution
  still need real Docker verification.
- Three target commits are pinned and checked out. Static audit verifies permissive licence
  texts and 1k-10k source lines (see `targets/static-audit.json`). Dependency validation,
  three repeated suite runs and one-minute runtime qualification remain pending.
- CoverUp generation is external. The adapter validates supplied provenance and cost but
  cannot attest to or limit that external producer's API requests. Full automatic CoverUp
  orchestration needs a metered API gateway or a version-specific budget hook.
- Triage offers an optional budgeted semantic LLM judge (`triage_judge: true`) and removes
  unrelated top-level tests while checking reproduction. The default conservatively records
  leads for review. Input-level delta debugging is not implemented. No historical bug-fix
  commits have been curated.
- AST call relationships are approximate, not a whole-program points-to analysis. Module
  dedupe does not detect overlapping tests in otherwise different modules.
- Fresh Docker containers trade startup speed for isolation; warm-container reuse and
  pytest-xdist inside individual jobs are not implemented. Parallelism is across mutants.
- H2/H4 need interpretation of per-round trajectories and policy logs. Automatic verdicts
  are deliberately limited; multi-repository aggregate inference is not implemented.
- Optional Could-tier Pynguin, mini-swe-agent, TestGenEval, Q-learning and web dashboard
  are not implemented. They are extensions, not silently simulated baseline results.
- No remote repository, branch protection, real CODEOWNERS handles, Projects board,
  milestones, hosted secrets or release tags were created. Templates are local only.
- No paid runs or full research campaign have been executed. Results from fake mode
  must never be used as H1-H5 evidence.

## Next verification gate

Install Docker; build the runner; run `HELIA_DOCKER_IMAGE=helia-runner:local pytest
tests/test_docker_integration.py`; fetch and qualify targets; freeze configuration and
review/tag source; supply model prices and credentials; prepare metered CoverUp bundles
and historical fixes; then run the three target configurations with ten seeds each.


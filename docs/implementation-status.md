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

- Docker Desktop is installed on the Windows host, but WSL is absent, so the Linux engine
  cannot start locally yet. The Docker image build, sandbox integration test and pinned
  target suite qualification pass in Linux CI. Windows/WSL execution still needs local
  verification after WSL is configured.
- Three target commits are pinned and checked out. Static audit verifies permissive licence
  texts and 1k-10k source lines (see `targets/static-audit.json`). CI runs their original
  suites three times in Docker, requires each to pass within one minute and uploads its
  runtime audit artifact. Target-specific dependency locks for broader configurations
  still need review beyond these passing baseline suites.
- CoverUp generation is external. The adapter validates supplied provenance and cost but
  cannot attest to or limit that external producer's API requests. Full automatic CoverUp
  orchestration needs a metered API gateway or a version-specific budget hook.
- Triage offers an optional budgeted semantic LLM judge (`triage_judge: true`) and removes
  unrelated top-level tests while checking reproduction. The default conservatively records
  leads for review. Input-level delta debugging is not implemented. A Toolz fix for
  `merge_with` is curated and its reverse-patch differential check passes in Linux CI;
  additional historical fixes would widen real-bug evaluation.
- AST call relationships are approximate, not a whole-program points-to analysis. Module
  dedupe does not detect overlapping tests in otherwise different modules.
- Fresh Docker containers trade startup speed for isolation; warm-container reuse and
  pytest-xdist inside individual jobs are not implemented. Parallelism is across mutants.
- H2/H4 need interpretation of per-round trajectories and policy logs. Automatic verdicts
  are deliberately limited; multi-repository aggregate inference is not implemented.
- Optional Could-tier Pynguin, mini-swe-agent, TestGenEval, Q-learning and web dashboard
  are not implemented. They are extensions, not silently simulated baseline results.
- The GitHub repository and CI exist. Branch protection, real CODEOWNERS handles, a Projects
  board, milestones, hosted LLM secrets and release tags remain pending.
- No paid runs or full research campaign have been executed. Results from fake mode
  must never be used as H1-H5 evidence.

## Next verification gate

Configure WSL and Docker Desktop locally, then rerun the Docker integration and target
qualification checks. Supply the Anthropic model, price, cap and key; prepare metered
CoverUp bundles; freeze and tag source/configuration; then run the three target
configurations with ten seeds each and write the measured hypothesis report.


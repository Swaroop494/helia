# Local validation

Validated on Windows with Python 3.12.10 on 2026-11-10:

- `pytest -q`: 38 passed, one Docker integration test skipped because Docker is unavailable.
- `ruff check .`: passed.
- `mypy src contracts`: passed across 21 source files.
- `helia schemas`: generated versioned JSON schemas.
- `helia run configs/demo.yaml`: completed five synthetic arms over three seeds.
- Real Cosmic Ray session creation and mutation application on trusted fixture source passed.
- Read-only static audit of three pinned target checkouts completed; all satisfy the source
  line range. Licence texts are retained in `targets/static-audit.json`.

No target test suite or generated test was executed on the host. No paid API calls were
made. Docker build/runtime, full target qualification, live generation and research claims
remain unverified locally. The Docker smoke test is wired into Linux CI but no hosted CI
run has been triggered from this local repository.

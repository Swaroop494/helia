# Local validation

Validated on Windows with Python 3.12.10 and Linux GitHub Actions on 2026-11-10:

- `pytest -q`: 38 passed, one Docker integration test skipped because Docker is unavailable.
- `ruff check .`: passed.
- `mypy src contracts`: passed across 21 source files.
- `helia schemas`: generated versioned JSON schemas.
- `helia run configs/demo.yaml`: completed five synthetic arms over three seeds.
- Real Cosmic Ray session creation and mutation application on trusted fixture source passed.
- Read-only static audit of three pinned target checkouts completed; all satisfy the source
  line range. Licence texts are retained in `targets/static-audit.json`.

Linux CI built the Docker runner, passed the non-root/network-off sandbox integration test,
ran each of the three pinned target suites three times within the one-minute limit and
confirmed a curated Toolz bug by passing on the fixed code and failing after reversing
its implementation patch. See [the passing CI run](https://github.com/Swaroop494/helia/actions/runs/42813421736)
and its target audit and historical evidence artifacts.

No target test suite or generated test was executed on the Windows host. Docker Desktop
requires WSL configuration there. No paid API calls were made, and no H1-H5 research
claim has been measured.

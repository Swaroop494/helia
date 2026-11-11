"""Static licence/size evidence plus isolated baseline and three reruns."""

from helia.io import digest
from helia.repo_index import build_index


def audit_target(config, executor):
    index = build_index(config.repo, config.source_dirs)
    licences = sorted(config.repo.glob("LICENSE*")) + sorted(config.repo.glob("COPYING*"))
    texts = {p.name: p.read_text(encoding="utf-8", errors="replace")
             for p in licences if p.is_file() and not p.is_symlink()}
    results = [executor.run(config.repo, {}) for _ in range(4)]
    signatures = [digest([r.outcome, r.test_outcomes, r.failures]) for r in results]
    return {
        "schema_version": 1,
        "repo": str(config.repo),
        "licence_texts": texts,
        "licence_review": "review required" if texts else "missing",
        "source_lines": sum(len((config.repo / p).read_text(encoding="utf-8").splitlines())
                            for p in index.files),
        "parse_errors": index.parse_errors,
        "test_times_s": [r.duration_s for r in results],
        "flaky": len(set(signatures)) > 1,
        "qualified": bool(texts) and not index.parse_errors
                     and all(r.outcome == "pass" and r.duration_s <= config.timeout_s
                             for r in results),
        "runs": [r.model_dump() for r in results],
    }

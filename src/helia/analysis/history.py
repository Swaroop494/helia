"""Real-bug confirmation using an isolated snapshot with a historical fix reverted."""

import subprocess
import tempfile
from pathlib import Path

from helia.io import snapshot


def verify_fix(repo: Path, fix_commit: str, generated: dict, executor, reruns: int = 3):
    """Require stable pass at the fix and stable failure after reverse-applying that fix."""

    def git(*args):
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True)

    commit = git("rev-parse", "--verify", fix_commit + "^{commit}").stdout.decode().strip()
    head = git("rev-parse", "HEAD").stdout.decode().strip()
    if commit != head or git("status", "--porcelain").stdout.strip():
        raise ValueError(
            "Historical verification requires a clean target checked out at the fix commit"
        )
    patch = git(
        "diff",
        commit + "^",
        commit,
        "--",
        *executor.source_dirs,
        ":(exclude)**/tests/**",
        ":(exclude)**/test/**",
    ).stdout
    if not patch:
        raise ValueError("Fix commit has no Python changes")
    with tempfile.TemporaryDirectory(prefix="helia-history-") as temp:
        broken = Path(temp) / "repo"
        snapshot(repo, broken)
        # git apply operates only on this disposable snapshot, never the user's repo.
        subprocess.run(
            ["git", "apply", "--reverse", "--whitespace=nowarn", "-"],
            input=patch,
            cwd=broken,
            check=True,
            capture_output=True,
        )
        fixed = [executor.run(repo, generated, tests=sorted(generated)) for _ in range(reruns)]
        reverted = [executor.run(broken, generated, tests=sorted(generated)) for _ in range(reruns)]
    from helia.analysis import killed

    confirmed = all(r.outcome == "pass" for r in fixed) and all(killed(r) for r in reverted)
    return {
        "fix_commit": commit,
        "confirmed": confirmed,
        "fixed": [r.model_dump() for r in fixed],
        "reverted": [r.model_dump() for r in reverted],
    }

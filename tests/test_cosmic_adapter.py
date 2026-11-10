"""Real Cosmic Ray parsing/mutation on trusted fixture source, no target execution."""

from pathlib import Path

from cosmic_ray.commands.init import init
from cosmic_ray.mutating import apply_mutation
from cosmic_ray.plugins import get_operator
from cosmic_ray.work_db import use_db

from helia.mutants import from_session
from helia.repo_index import build_index


def test_cosmic_session_and_mutation(tmp_path):
    source = tmp_path / "toy.py"
    source.write_text("def add(a, b):\n    return a + b\n")
    db_path = tmp_path / "session.sqlite"
    with use_db(db_path) as db:
        init([source], db, {})
    mutants = from_session(db_path, tmp_path, build_index(tmp_path, ["toy.py"]))
    assert mutants
    original = source.read_text()
    m = mutants[0]
    before, after = apply_mutation(
        Path(tmp_path / m.file), get_operator(m.operator)(**m.operator_args), m.occurrence
    )
    assert before == original and after != original and after is not None

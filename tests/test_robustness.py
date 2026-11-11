import sys

import pytest

from helia.cli import main
from helia.controller.config import Config
from helia.generator import validate_response
from helia.repo_index import build_index


def test_index_supports_python_encoding_and_records_bad_files(tmp_path):
    (tmp_path / "latin.py").write_bytes(b"# coding: latin-1\nname = '\xe9'\n")
    (tmp_path / "bad.py").write_bytes(b"value = '\xff'\n")
    index = build_index(tmp_path, ["."])
    assert index.files == ["latin.py"]
    assert "bad.py" in index.parse_errors


def test_index_prunes_ignored_trees_and_enforces_limits(tmp_path):
    ignored = tmp_path / ".venv"
    ignored.mkdir()
    (ignored / "large.py").write_text("x" * 100)
    (tmp_path / "small.py").write_text("x = 1\n")
    assert build_index(tmp_path, ["."], max_file_bytes=10).files == ["small.py"]
    with pytest.raises(ValueError, match="file limit"):
        build_index(tmp_path, ["."], max_files=0)
    with pytest.raises(ValueError, match="byte limit"):
        build_index(tmp_path, ["."], max_file_bytes=2)
    with pytest.raises(ValueError, match="total index"):
        build_index(tmp_path, ["."], max_total_bytes=2)


@pytest.mark.parametrize("source", [
    "def helper():\n def test_nested():\n  assert True",
    "class Helper:\n def test_hidden(self):\n  assert True",
    "assert True\ndef test_empty():\n pass",
    "class TestBad:\n def __init__(self): pass\n def test_x(self): assert True",
])
def test_validation_requires_collectible_asserting_tests(source):
    with pytest.raises(ValueError, match="no test"):
        validate_response(source, set())


def test_validation_counts_methods_but_not_nested_tests():
    source = "class TestGood:\n def test_x(self):\n  assert True\n  def test_nested(): pass"
    assert validate_response(source, set())[2] == 1


def test_overlap_dedupe_checks_support_context():
    accepted = "from alpha import f\ndef test_a():\n assert f(1) == 1\n"
    candidate = (
        "from alpha import f\ndef test_renamed():\n assert f(1) == 1\n"
        "def test_new():\n assert f(2) == 2\n"
    )
    with pytest.raises(ValueError, match="overlaps"):
        validate_response(candidate, set(), [accepted])
    assert validate_response(candidate.replace("alpha", "beta"), set(), [accepted])[2] == 2


def test_paths_are_portable_and_distinct(tmp_path):
    assert Config(repo=tmp_path, backend="fake", source_dirs=["src\\pkg"]).source_dirs == [
        "src/pkg"
    ]
    with pytest.raises(ValueError, match="Duplicate repository paths"):
        Config(repo=tmp_path, backend="fake", tests=["tests", "./tests"])


def test_prompt_limit_includes_large_target_source(tmp_path):
    from helia.generator import build_prompt

    (tmp_path / "large.py").write_text("def large():\n" + "    x = 1\n" * 100)
    index = build_index(tmp_path, ["."])
    assert len(build_prompt(index, index.regions[0], "boundary", max_chars=500)) == 500


def test_cli_yaml_error_is_concise(tmp_path, monkeypatch, capsys):
    config = tmp_path / "bad.yaml"
    config.write_text("repo: [")
    monkeypatch.setattr(sys, "argv", ["helia", "run", str(config), "--dry-run"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    assert "helia:" in capsys.readouterr().err


def test_cli_matrix_failure_returns_nonzero(monkeypatch, capsys):
    monkeypatch.setattr("helia.controller.matrix.run_matrix", lambda *a, **kw: iter([
        {"error": "failed"}, {"run_dir": "completed"}
    ]))
    monkeypatch.setattr(sys, "argv", ["helia", "experiment", "config.yaml"])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    assert "completed" in capsys.readouterr().out

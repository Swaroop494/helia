"""M1: static repository index and dynamic test selection."""

import ast
import os
import tokenize
from pathlib import Path

from contracts.models import Region, RepoIndex
from helia.io import IGNORE


def build_index(
    root: Path, source_dirs: list[str], *, max_file_bytes: int = 2_000_000,
    max_total_bytes: int = 50_000_000, max_files: int = 10000,
) -> RepoIndex:
    """Parse without importing target code; unresolved call names remain explicit."""
    regions, files, fixtures, tests, errors = [], [], {}, {}, {}
    total_bytes = 0
    paths = []
    for directory, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in IGNORE
                         and not Path(directory, d).is_symlink())
        for name in sorted(names):
            if name.endswith(".py"):
                paths.append(Path(directory, name))
                if len(paths) > max_files:
                    raise ValueError(f"Repository exceeds index file limit ({max_files})")
    for path in sorted(paths):
        relative = path.relative_to(root)
        if path.is_symlink() or any(p in IGNORE for p in relative.parts):
            continue
        name = relative.as_posix()
        try:
            size = path.stat().st_size
            if size > max_file_bytes:
                raise ValueError(f"Source file exceeds index byte limit: {name}")
            total_bytes += size
            if total_bytes > max_total_bytes:
                raise ValueError("Repository exceeds total index byte limit")
            with tokenize.open(path) as stream:
                source = stream.read()
            tree = ast.parse(source)
        except (SyntaxError, UnicodeError, OSError, RecursionError) as exc:
            errors[name] = str(exc)
            continue
        is_test = (
            path.name.startswith("test_")
            or path.name == "conftest.py"
            or any(part in {"tests", "test"} for part in relative.parts[:-1])
        )
        if is_test:
            tests[name] = source
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
                    "fixture" in ast.unparse(d) for d in node.decorator_list
                ):
                    fixtures[f"{name}::{node.name}"] = ast.get_source_segment(source, node) or ""
            continue
        if not any(
            relative == Path(d) or Path(d) in relative.parents or d == "." for d in source_dirs
        ):
            continue
        files.append(name)

        def visit(nodes, prefix=""):
            for node in nodes:
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    qualified = prefix + node.name
                    regions.append(
                        Region(
                            id=f"{name}::{qualified}",
                            file=name,
                            name=qualified,
                            line=node.lineno,
                            end_line=node.end_lineno or node.lineno,
                            source=ast.get_source_segment(source, node) or "",
                            calls=sorted(
                                {
                                    ast.unparse(n.func)
                                    for n in ast.walk(node)
                                    if isinstance(n, ast.Call)
                                }
                            ),
                        )
                    )
                    visit(node.body, qualified + ".")

        visit(tree.body)
        if not any(r.file == name for r in regions):
            regions.append(
                Region(
                    id=f"{name}::<module>",
                    file=name,
                    name="<module>",
                    line=1,
                    end_line=max(1, len(source.splitlines())),
                    source=source,
                )
            )
    return RepoIndex(
        regions=regions, files=files, fixtures=fixtures, tests=tests, parse_errors=errors
    )


def region_for(index: RepoIndex, file: str, line: int) -> str:
    candidates = [r for r in index.regions if r.file == file and r.line <= line <= r.end_line]
    return (
        min(candidates, key=lambda r: r.end_line - r.line).id if candidates else f"{file}::<module>"
    )


def select_tests(contexts: dict, file: str, line: int) -> list[str] | None:
    """None means unknown coverage (run full suite); [] means known uncovered."""
    if file not in contexts:
        return None
    entries = contexts[file].get(str(line), [])
    if "" in entries or any("::" not in c for c in entries):
        return None  # import/session fixtures cannot safely be attributed to one test
    return sorted({c.split("|", 1)[0] for c in entries})

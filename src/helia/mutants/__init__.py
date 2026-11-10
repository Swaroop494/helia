"""M2: Cosmic Ray adapter and deterministic stratified sampling."""

import random
from collections import defaultdict
from pathlib import Path

from contracts.models import Mutant, RepoIndex
from helia.io import digest
from helia.repo_index import region_for


def from_session(database: Path, root: Path, index: RepoIndex) -> list[Mutant]:
    from cosmic_ray.work_db import WorkDB, use_db

    mutants = []
    with use_db(database, WorkDB.Mode.open) as db:
        for work in db.work_items:
            if len(work.mutations) != 1:
                raise ValueError("Only first-order mutants are supported")
            spec = work.mutations[0]
            path = Path(spec.module_path)
            file = path.relative_to(root).as_posix() if path.is_absolute() else path.as_posix()
            if file not in index.files:
                continue
            identity = [file, spec.operator_name, spec.occurrence]
            mutants.append(
                Mutant(
                    id=digest(identity)[:24],
                    file=file,
                    line=spec.start_pos[0],
                    operator=spec.operator_name,
                    occurrence=spec.occurrence,
                    operator_args=getattr(spec, "operator_args", {}),
                    region=region_for(index, file, spec.start_pos[0]),
                )
            )
    return mutants


def sample(
    mutants: list[Mutant], seed: int, total: int, per_file: int, heldout_fraction: float = 0.3
) -> list[Mutant]:
    """Round-robin across files then functions; split before any execution feedback."""
    rng = random.Random(seed)
    groups: dict = defaultdict(lambda: defaultdict(list))
    for mutant in sorted(mutants, key=lambda m: m.id):
        groups[mutant.file][mutant.region].append(mutant)
    for regions in groups.values():
        for values in regions.values():
            rng.shuffle(values)
    selected: list[Mutant] = []
    counts: dict[str, int] = defaultdict(int)
    while len(selected) < total:
        progress = False
        files = sorted(groups)
        rng.shuffle(files)
        for file in files:
            regions = [r for r, ms in groups[file].items() if ms]
            if not regions or counts[file] >= per_file or len(selected) >= total:
                continue
            # Least represented region first, seeded tie-breaking.
            rng.shuffle(regions)
            region = min(regions, key=lambda r: sum(m.region == r for m in selected))
            selected.append(groups[file][region].pop())
            counts[file] += 1
            progress = True
        if not progress:
            break
    rng.shuffle(selected)
    heldout_count = max(1, round(len(selected) * heldout_fraction)) if len(selected) > 1 else 0
    return [
        m.model_copy(update={"split": "heldout" if i < heldout_count else "feedback"})
        for i, m in enumerate(selected)
    ]

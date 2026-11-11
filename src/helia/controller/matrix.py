"""Repository x arm x seed runs with independent identities and resumable outputs."""

from helia.controller import run_experiment
from helia.controller.config import load_config


def run_matrix(paths, *, live=False):
    # Validate all inputs before starting any work.
    configs = [load_config(path.resolve()) for path in paths]
    for config in configs:
        for arm in config.arms:
            for seed in config.seeds:
                values = config.model_dump()
                values.update(arms=[arm], seeds=[seed])
                single = type(config).model_validate(values)
                try:
                    directory = run_experiment(single, live=live)
                    yield {"arm": arm, "seed": seed, "run_dir": str(directory)}
                except (RuntimeError, ValueError, OSError) as exc:
                    yield {"repo": str(config.repo), "arm": arm, "seed": seed,
                           "error": str(exc)}

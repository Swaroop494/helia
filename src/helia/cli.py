"""Command-line entry points; execution is Docker-only except explicit synthetic demos."""

import argparse
import json
import subprocess
from pathlib import Path

from helia.controller import run_experiment
from helia.controller.config import load_config
from helia.io import write_json
from helia.repo_index import build_index


def main():
    parser = argparse.ArgumentParser(prog="helia", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Check local prerequisites without executing target code")
    matrix = commands.add_parser("experiment", help="Resume a repository/arm/seed matrix")
    matrix.add_argument("configs", type=Path, nargs="+")
    matrix.add_argument("--live", action="store_true")
    for name in ["run", "index", "sensitivity"]:
        cmd = commands.add_parser(name)
        cmd.add_argument("config", type=Path)
        if name == "run":
            cmd.add_argument("--run-id")
            mode = cmd.add_mutually_exclusive_group()
            mode.add_argument("--live", action="store_true")
            mode.add_argument("--dry-run", action="store_true")
        if name == "sensitivity":
            cmd.add_argument("--exploration", type=float, nargs="+", default=[0, 0.15, 0.3])
            cmd.add_argument("--kill-weight", type=float, nargs="+", default=[0.5, 1, 2])
    for name in ["report", "plot"]:
        commands.add_parser(name).add_argument("run_dir", type=Path)
    schemas = commands.add_parser("schemas")
    schemas.add_argument("output", type=Path, nargs="?", default=Path("contracts/schemas"))
    history = commands.add_parser("verify-fix")
    history.add_argument("config", type=Path)
    history.add_argument("commit")
    history.add_argument("generated", type=Path)
    history.add_argument("--output", type=Path, default=Path("bug-verification.json"))
    args = parser.parse_args()
    try:
        if args.command == "doctor":
            from helia.diagnostics import doctor

            print(json.dumps(doctor(), indent=2))
        elif args.command == "experiment":
            from helia.controller.matrix import run_matrix

            for result in run_matrix(args.configs, live=args.live):
                print(json.dumps(result))
        elif args.command == "schemas":
            import contracts.models as models

            for name in [
                "Mutant",
                "ExecResult",
                "RepoIndex",
                "Failure",
                "BugLead",
                "LLMResponse",
                "Metrics",
            ]:
                write_json(
                    args.output / (name + ".json"), getattr(models, name).model_json_schema()
                )
            print(args.output.resolve())
        elif args.command in {"report", "plot"}:
            from helia.controller.report import plot, report

            print((report if args.command == "report" else plot)(args.run_dir).resolve())
        else:
            config = load_config(args.config.resolve())
            if args.command == "index":
                print(build_index(config.repo, config.source_dirs).model_dump_json(indent=2))
            elif args.command == "run":
                if args.dry_run:
                    print(config.model_dump_json(indent=2))
                else:
                    print(run_experiment(config, args.run_id, live=args.live))
            elif args.command == "sensitivity":
                for exploration in args.exploration:
                    for weight in args.kill_weight:
                        values = config.model_dump()
                        values.update(exploration=exploration, reward_kills=weight)
                        print(run_experiment(type(config).model_validate(values)))
            else:
                from helia.analysis.history import verify_fix
                from helia.executor import DockerExecutor

                executor = DockerExecutor(
                    config.image, config.source_dirs, config.tests, config.timeout_s, config.workers
                )
                result = verify_fix(
                    config.repo,
                    args.commit,
                    json.loads(args.generated.read_text()),
                    executor,
                    config.reruns,
                )
                write_json(args.output, result)
                print(args.output.resolve())
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"helia: {exc}\n")


if __name__ == "__main__":
    main()

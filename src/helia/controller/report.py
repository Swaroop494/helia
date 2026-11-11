"""CSV exports and conservative, paired hypothesis assessments."""

import csv
import json
import random
import statistics
from pathlib import Path

from helia.controller.html_report import write_html
from helia.controller.metrics import summarize
from helia.io import write_json


def paired_interval(a: dict, b: dict, seed: int = 0) -> dict:
    common = sorted(a.keys() & b.keys())
    differences = [a[s] - b[s] for s in common]
    if len(differences) < 2:
        return {"n": len(differences), "verdict": "insufficient evidence"}
    rng = random.Random(seed)
    means = sorted(
        statistics.mean(rng.choices(differences, k=len(differences))) for _ in range(2000)
    )
    low, high = means[49], means[1949]
    return {
        "n": len(common),
        "mean_difference": statistics.mean(differences),
        "ci95": [low, high],
        "verdict": "supported" if low > 0 else "not supported" if high < 0 else "inconclusive",
    }


def report(run_dir: Path) -> Path:
    manifest = json.loads((run_dir / "manifest.json").read_text())
    rows, finals = [], []
    for path in sorted(run_dir.glob("seed-*/*/complete.json")):
        finals.append(json.loads(path.read_text())["final"])
        rows.extend(json.loads((path.parent / "metrics.json").read_text()))
    if not rows:
        raise ValueError("No completed arms to report")
    summary = summarize(finals)
    write_json(run_dir / "arm-summary.json", summary)
    with (run_dir / "metrics.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    def values(arm, measure):
        result = {}
        for row in finals:
            if row["arm"] == arm:
                value = measure(row)
                if value is not None:
                    result[row["seed"]] = value
        return result

    def compare(a, b, measure):
        return paired_interval(values(a, measure), values(b, measure))

    def mutation(r):
        return r["heldout_killed"] / r["heldout_total"] if r["heldout_total"] else None

    def efficiency(r):
        return r["heldout_killed"] / r["cost_usd"] if r["cost_usd"] > 0 else None

    hypotheses = {
        "H1_guided_vs_one_shot": compare("guided", "one-shot", mutation),
        "H1_guided_vs_repo": compare("guided", "repo", mutation),
        "H2_unique_failures": compare("guided", "one-shot", lambda r: r["unique_failures"]),
        "H3_coverage": compare("guided", "repo", lambda r: r["coverage"]),
        "H4_guided_vs_random": compare("guided", "random", mutation),
        "H5_kills_per_dollar": compare("guided", "coverup", efficiency),
    }
    if manifest["synthetic"]:
        for value in hypotheses.values():
            value["verdict"] = "synthetic data; no research conclusion"
    write_json(run_dir / "hypotheses.json", hypotheses)
    lines = [
        "# Helia experiment report",
        "",
        "SYNTHETIC DEMO - NOT RESEARCH EVIDENCE"
        if manifest["synthetic"]
        else "Measured Docker experiment",
        "",
        f"Target fingerprint: `{manifest['target_hash']}`",
        "",
        "All scores use a fixed sampled split. Held-out results never enter generation or policy updates.",
        "",
        "## Hypotheses",
        "",
    ]
    lines.extend(
        f"- {name}: {result['verdict']} (paired seeds: {result['n']})"
        for name, result in hypotheses.items()
    )
    lines += [
        "",
        "## Interpretation and limitations",
        "",
        "Intervals are paired bootstrap estimates across seeds, not proof of causation. "
        "Timeouts, collection failures and infrastructure errors are not mutant kills. "
        "Zero-cost runs have undefined dollar efficiency. Equivalent mutants are not removed. "
        "Stable failures on original code are leads until independently confirmed.",
        "",
        "H2 exports cumulative unique signatures; consult per-round CSV for the discovery rate. "
        "H4's score comparison is only one part of the hypothesis: inspect policy histories for "
        "weight shifts and learning curves. No causal policy claim is made automatically.",
        "",
        "Raw provenance, cost ledgers, generated tests, triage evidence and per-round results are stored alongside this report.",
    ]
    output = run_dir / "report.md"
    lines += write_html(run_dir, lines, rows, summary)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def plot(run_dir: Path) -> Path:
    """Optional publication-ready PNG learning curves from saved measurements."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    with (run_dir / "metrics.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
    for arm in sorted({r["arm"] for r in rows}):
        rounds = sorted({int(r["round"]) for r in rows if r["arm"] == arm})
        for ax, key in zip(axes, ["feedback_killed", "coverage"]):
            means = [
                statistics.mean(
                    float(r[key]) for r in rows if r["arm"] == arm and int(r["round"]) == n
                )
                for n in rounds
            ]
            ax.plot(rounds, means, marker="o", label=arm)
            ax.set(xlabel="Round", ylabel=key.replace("_", " "))
            ax.legend()
    manifest = json.loads((run_dir / "manifest.json").read_text())
    fig.suptitle("Helia - synthetic demo" if manifest["synthetic"] else "Helia experiment")
    output = run_dir / "learning-curves.png"
    fig.savefig(output, dpi=180)
    plt.close(fig)
    return output

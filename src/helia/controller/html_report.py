"""Dependency-free, escaped HTML and SVG reports from recorded measurements."""

import html
import statistics


def comparison(summary):
    headers = ["Arm", "Seeds", "Held-out score", "95% CI", "Valid-test rate", "$/kill"]

    def number(value):
        return "N/A" if value is None else f"{value:.4f}"

    rows = []
    for arm, values in summary["arms"].items():
        ci = values["heldout_score_ci95"]
        rows.append([arm, str(values["seeds"]), number(values["heldout_score"]),
                     "N/A" if ci is None else f"[{number(ci[0])}, {number(ci[1])}]",
                     number(values["valid_test_rate"]), number(values["cost_per_killed_mutant"])])
    return headers, rows


def curves(rows):
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 360" role="img">',
             '<title>Feedback kills and coverage by round; means across seeds</title>',
             '<rect width="960" height="360" fill="white"/>']
    colors = ["#1565c0", "#c62828", "#2e7d32", "#6a1b9a", "#a65b00"]
    arms = sorted({r["arm"] for r in rows})
    for panel, key in enumerate(["feedback_killed", "coverage"]):
        left = 55 + panel * 480
        max_round = max(1, max(r["round"] for r in rows))
        maximum = max(1, max(r[key] for r in rows))
        parts += [f'<path d="M{left} 35 V270 H{left + 390}" fill="none" stroke="#555"/>',
                  f'<text x="{left}" y="20">{key.replace("_", " ")} (seed mean)</text>',
                  f'<text x="{left}" y="290">0</text>',
                  f'<text x="{left + 330}" y="290">Round {max_round}</text>',
                  f'<text x="{left - 40}" y="45">{maximum:g}</text>']
        for i, arm in enumerate(arms):
            rounds = sorted({r["round"] for r in rows if r["arm"] == arm})
            points = []
            for n in rounds:
                mean = statistics.mean(r[key] for r in rows if r["arm"] == arm and r["round"] == n)
                points.append(f"{left + 390 * n / max_round:.2f},{270 - 225 * mean / maximum:.2f}")
            color = colors[i % len(colors)]
            parts.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" '
                         'stroke-width="2"/>')
            if panel == 0:
                parts.append(f'<text x="{40 + i * 175}" y="330" fill="{color}">'
                             f'{html.escape(arm)}</text>')
    return "".join(parts) + "</svg>"


def write_html(run_dir, lines, rows, summary):
    headers, data = comparison(summary)
    svg = curves(rows)
    (run_dir / "learning-curves.svg").write_text(svg, encoding="utf-8")
    table = "<table><thead><tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    table += "</tr></thead><tbody>"
    for row in data:
        table += "<tr>" + "".join(f"<td>{html.escape(v)}</td>" for v in row) + "</tr>"
    table += "</tbody></table>"
    document = ('<!doctype html><html lang="en"><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1">'
                '<title>Helia experiment report</title><style>'
                'body{font:16px system-ui;max-width:1100px;margin:2em auto;padding:1em}'
                'table{border-collapse:collapse}td,th{border:1px solid #aaa;padding:.6em}'
                'svg{width:100%}pre{white-space:pre-wrap}</style><body>'
                '<h1>Helia experiment report</h1>'
                + table + svg + '<pre>' + html.escape("\n".join(lines)) + '</pre></body></html>')
    (run_dir / "report.html").write_text(document, encoding="utf-8")
    return ["", "## Per-arm comparison", "", "| " + " | ".join(headers) + " |",
            "| " + " | ".join(["---"] * len(headers)) + " |",
            *["| " + " | ".join(row) + " |" for row in data], "",
            "![Learning curves](learning-curves.svg)", "",
            "Intervals resample seeds; N/A means insufficient data or an undefined denominator."]

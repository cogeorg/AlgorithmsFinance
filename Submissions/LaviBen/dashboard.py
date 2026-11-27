"""Build a self-contained HTML dashboard from fixed-input benchmark JSON."""

from __future__ import annotations

import argparse
import html
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


COLORS = ("#2563eb", "#9333ea", "#ea580c", "#059669")


def _format_ms(value: float) -> str:
    if value < 0.01:
        return f"{value:.6f}"
    if value < 1:
        return f"{value:.4f}"
    return f"{value:.2f}"


def _chart_svg(records: list[dict[str, Any]]) -> str:
    width, height = 620, 310
    left, right, top, bottom = 70, 20, 20, 56
    chart_width = width - left - right
    chart_height = height - top - bottom
    sizes = sorted({int(record["array_size"]) for record in records})
    algorithms = list(dict.fromkeys(str(record["algorithm"]) for record in records))
    grouped: dict[str, dict[int, float]] = defaultdict(dict)

    for record in records:
        grouped[str(record["algorithm"])][int(record["array_size"])] = max(
            float(record["combined_median_ms"]),
            1e-9,
        )

    values = [value for series in grouped.values() for value in series.values()]
    log_min = math.log10(min(values))
    log_max = math.log10(max(values))
    if math.isclose(log_min, log_max):
        log_min -= 0.5
        log_max += 0.5

    def x_position(index: int) -> float:
        if len(sizes) == 1:
            return left + chart_width / 2
        return left + index * chart_width / (len(sizes) - 1)

    def y_position(value: float) -> float:
        proportion = (math.log10(value) - log_min) / (log_max - log_min)
        return top + chart_height * (1 - proportion)

    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Combined median runtime by fixed input size">'
    ]
    for tick_index in range(5):
        proportion = tick_index / 4
        tick_log = log_min + (log_max - log_min) * proportion
        tick_value = 10**tick_log
        y = top + chart_height * (1 - proportion)
        parts.append(
            f'<line x1="{left}" y1="{y:.2f}" x2="{width - right}" '
            f'y2="{y:.2f}" class="grid" />'
        )
        parts.append(
            f'<text x="{left - 8}" y="{y + 4:.2f}" text-anchor="end" '
            f'class="axis-label">{html.escape(_format_ms(tick_value))}</text>'
        )

    for index, size in enumerate(sizes):
        x = x_position(index)
        parts.append(
            f'<text x="{x:.2f}" y="{height - 30}" text-anchor="middle" '
            f'class="axis-label">{size:,}</text>'
        )

    for algorithm_index, algorithm in enumerate(algorithms):
        color = COLORS[algorithm_index % len(COLORS)]
        points = [
            (x_position(index), y_position(grouped[algorithm][size]))
            for index, size in enumerate(sizes)
        ]
        point_text = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
        parts.append(
            f'<polyline points="{point_text}" fill="none" stroke="{color}" '
            'stroke-width="3" stroke-linejoin="round" />'
        )
        for x, y in points:
            parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="{color}" />')

    parts.extend(
        (
            f'<text x="{left + chart_width / 2:.2f}" y="{height - 4}" '
            'text-anchor="middle" class="axis-title">Array entries (n)</text>',
            f'<text x="16" y="{top + chart_height / 2:.2f}" '
            'text-anchor="middle" class="axis-title" '
            f'transform="rotate(-90 16 {top + chart_height / 2:.2f})">'
            'Combined ms (log)</text>',
            "</svg>",
        )
    )
    return "".join(parts)


def build_dashboard(results_path: Path, output_path: Path) -> Path:
    """Read benchmark JSON and write a portable fixed-input dashboard."""

    payload = json.loads(results_path.read_text(encoding="utf-8"))
    summary = payload.get("summary", [])
    cases = payload.get("cases", [])
    raw_results = payload.get("raw_results", [])
    metadata = payload.get("metadata", {})
    if not summary or not cases or not raw_results:
        raise ValueError("benchmark JSON is missing cases, raw results, or summary")

    settings = metadata["benchmark_settings"]
    environment = metadata["environment"]
    code_version = metadata["code_version"]
    largest_size = max(int(record["array_size"]) for record in summary)
    focus_query_count = max(int(record["query_count"]) for record in summary)
    available_scenarios = {str(record["scenario"]) for record in summary}
    focus_scenario = "mixed" if "mixed" in available_scenarios else min(available_scenarios)
    focus_rows = [
        record
        for record in summary
        if int(record["array_size"]) == largest_size
        and int(record["query_count"]) == focus_query_count
        and record["scenario"] == focus_scenario
    ]
    fastest = min(focus_rows, key=lambda record: float(record["combined_median_ms"]))

    algorithms = list(dict.fromkeys(str(record["algorithm"]) for record in summary))
    legend_items = "".join(
        f'<span><i style="background:{COLORS[index % len(COLORS)]}"></i>'
        f'{html.escape(algorithm)}</span>'
        for index, algorithm in enumerate(algorithms)
    )

    chart_panels: list[str] = []
    for query_count in settings["query_counts"]:
        for scenario in settings["scenarios"]:
            records = [
                record
                for record in summary
                if int(record["query_count"]) == int(query_count)
                and record["scenario"] == scenario
            ]
            chart_panels.append(
                '<article class="chart-card">'
                f'<h3>q={int(query_count):,} · {html.escape(str(scenario))}</h3>'
                f'{_chart_svg(records)}</article>'
            )

    table_rows = "".join(
        "<tr>"
        f'<td>{int(record["array_size"]):,}</td>'
        f'<td>{int(record["query_count"]):,}</td>'
        f'<td>{html.escape(str(record["scenario"]))}</td>'
        f'<td>{html.escape(str(record["algorithm"]))}</td>'
        f'<td>{_format_ms(float(record["preparation_median_ms"]))}</td>'
        f'<td>{_format_ms(float(record["query_batch_median_ms"]))}</td>'
        f'<td>{_format_ms(float(record["combined_median_ms"]))}</td>'
        "</tr>"
        for record in sorted(
            summary,
            key=lambda row: (
                int(row["array_size"]),
                int(row["query_count"]),
                str(row["scenario"]),
                str(row["algorithm"]),
            ),
        )
    )

    document = f"""<!doctype html>
<html lang="en"><head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LaviBen fixed-input runtime dashboard</title>
  <style>
    :root {{ color-scheme:light; --ink:#172033; --muted:#64748b; --panel:#fff; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:#f1f5f9; color:var(--ink); font:15px/1.5 system-ui,sans-serif; }}
    main {{ width:min(1400px,calc(100% - 32px)); margin:32px auto 56px; }}
    h1 {{ margin:0; font-size:clamp(28px,4vw,44px); letter-spacing:-.03em; }}
    h2 {{ margin:0 0 12px; font-size:20px; }} h3 {{ margin:0 0 4px; font-size:16px; }}
    .subtitle,.note {{ color:var(--muted); }}
    .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:14px; }}
    .card,.panel,.chart-card {{
      background:var(--panel); border:1px solid #dbe3ee; border-radius:16px;
      box-shadow:0 8px 24px #0f172a0d;
    }}
    .card {{ padding:18px; }} .card b {{ display:block; font-size:22px; margin-top:4px; }}
    .label {{
      color:var(--muted); font-size:12px; text-transform:uppercase;
      letter-spacing:.08em;
    }}
    .panel {{ margin-top:18px; padding:20px; overflow:auto; }}
    .chart-grid {{
      display:grid; grid-template-columns:repeat(auto-fit,minmax(460px,1fr));
      gap:14px;
    }}
    .chart-card {{ padding:14px; overflow:auto; }}
    svg {{ width:100%; min-width:460px; display:block; }}
    .grid {{ stroke:#dbe3ee; stroke-width:1; }} .axis-label {{ fill:#64748b; font-size:11px; }}
    .axis-title {{ fill:#334155; font-size:12px; font-weight:600; }}
    .legend {{ display:flex; flex-wrap:wrap; gap:12px 20px; margin-bottom:14px; }}
    .legend span {{ display:flex; align-items:center; gap:7px; }}
    .legend i {{ width:11px; height:11px; border-radius:50%; }}
    table {{ width:100%; border-collapse:collapse; white-space:nowrap; }}
    th,td {{ padding:9px 11px; border-bottom:1px solid #e2e8f0; text-align:right; }}
    th {{ color:#475569; font-size:11px; text-transform:uppercase; letter-spacing:.04em; }}
    th:nth-child(3),td:nth-child(3),th:nth-child(4),td:nth-child(4) {{ text-align:left; }}
  </style>
</head><body><main>
  <h1>Search runtime dashboard</h1>
  <p class="subtitle">Fixed, fingerprinted inputs shared by every method and version.</p>
  <section class="cards">
    <div class="card"><span class="label">Fixed cases</span><b>{len(cases)}</b></div>
    <div class="card"><span class="label">Raw timing rows</span><b>{len(raw_results):,}</b></div>
    <div class="card"><span class="label">Largest array</span><b>{largest_size:,}</b></div>
    <div class="card">
      <span class="label">Fastest · n={largest_size:,},
        q={focus_query_count:,}, {html.escape(focus_scenario)}</span>
      <b>{html.escape(str(fastest["algorithm"]))}</b>
    </div>
  </section>
  <section class="panel"><h2>Combined runtime scaling</h2>
    <div class="legend">{legend_items}</div>
    <div class="chart-grid">{"".join(chart_panels)}</div>
    <p class="note">Each line uses median combined time over
      {settings["repeats"]} repeats. Combined time includes preparation and the
      complete query batch. The y-axis is logarithmic.</p>
  </section>
  <section class="panel"><h2>Preparation, query batch, and combined medians</h2>
    <table><thead><tr><th>n</th><th>q</th><th>Scenario</th><th>Algorithm</th>
      <th>Preparation median (ms)</th><th>Query batch median (ms)</th><th>Combined median (ms)</th>
    </tr></thead><tbody>{table_rows}</tbody></table>
  </section>
  <section class="panel"><h2>Reproducibility metadata</h2>
    <p>Python {html.escape(str(environment["python_version"]))} ·
      {html.escape(str(environment["system"]))}
      {html.escape(str(environment["system_release"]))} ·
      {html.escape(str(environment["machine"]))} ·
      {environment["logical_cpu_count"]} logical CPUs</p>
    <p>Git commit
      <code>{html.escape(str(code_version["git_commit"]))}</code> · source
      SHA-256 <code>{html.escape(str(code_version["source_sha256"]))}</code></p>
    <p>Base seed {settings["base_seed"]}; case-specific seeds and input SHA-256
      digests are saved in <code>input_manifest.json</code>. Raw units are
      nanoseconds; summary units are milliseconds.</p>
  </section>
</main></body></html>
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("results/benchmark_results.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/runtime_dashboard.html"),
    )
    arguments = parser.parse_args()
    output_path = build_dashboard(arguments.input, arguments.output)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()

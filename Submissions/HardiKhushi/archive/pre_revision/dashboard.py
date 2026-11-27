"""Generate an offline HTML dashboard from CSVs saved under results/."""

import csv
from html import escape
from pathlib import Path


COLORS = {"linear": "#2563eb", "binary": "#a21caf", "set": "#047857"}


def chart(rows, metric, title, unit, divisor=1):
    sizes = sorted({int(row["n"]) for row in rows})
    maximum = max(float(row[metric]) / divisor for row in rows) or 1
    maximum *= 1.1
    left, top, width, height = 76, 28, 600, 240

    def x(n):
        if len(sizes) == 1:
            return left + width / 2
        return left + width * (n - sizes[0]) / (sizes[-1] - sizes[0])

    def y(value):
        return top + height * (1 - value / maximum)

    parts = [f'<svg viewBox="0 0 720 330" role="img" aria-label="{escape(title)}">',
             f'<title>{escape(title)} ({unit})</title>']
    for i in range(5):
        value = maximum * i / 4
        position = y(value)
        parts.append(f'<line x1="{left}" y1="{position}" x2="{left + width}" '
                     f'y2="{position}" stroke="#dbe3ed"/>')
        parts.append(f'<text x="{left - 10}" y="{position + 4}" '
                     f'text-anchor="end">{value:.3g}</text>')
    for n in sizes:
        parts.append(f'<text x="{x(n)}" y="290" text-anchor="middle">{n:,}</text>')
    parts.append(f'<text x="{left}" y="16">{unit}</text>')
    parts.append('<text x="376" y="320" text-anchor="middle">Input IDs (n)</text>')
    for name, color in COLORS.items():
        series = sorted((row for row in rows if row["algorithm"] == name),
                        key=lambda row: int(row["n"]))
        points = [(x(int(row["n"])), y(float(row[metric]) / divisor)) for row in series]
        coordinates = " ".join(f"{px},{py}" for px, py in points)
        parts.append(f'<polyline points="{coordinates}" fill="none" '
                     f'stroke="{color}" stroke-width="3"/>')
        for row, (px, py) in zip(series, points):
            label = f'{name}: n={row["n"]}, {float(row[metric]) / divisor:.4g} {unit}'
            parts.append(f'<circle cx="{px}" cy="{py}" r="5" fill="{color}">'
                         f'<title>{escape(label)}</title></circle>')
    parts.append('</svg>')
    return "".join(parts)


def generate_dashboard(directory):
    def read(name):
        with (directory / "results" / name).open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    timing, memory = read("timing.csv"), read("memory.csv")
    peaks = {(row["algorithm"], row["n"]): row for row in memory}
    table_rows = []
    for row in timing:
        peak = peaks[(row["algorithm"], row["n"])]
        table_rows.append(
            f'<tr><td>{escape(row["algorithm"])}</td><td>{int(row["n"]):,}</td>'
            f'<td>{int(row["queries"]):,}</td><td>{float(row["median_ms"]):.4f}</td>'
            f'<td>{float(row["min_ms"]):.4f}–{float(row["max_ms"]):.4f}</td>'
            f'<td>{float(peak["median_peak_bytes"]) / 1024:.2f}</td></tr>')
    first = timing[0]
    legend = " ".join(f'<span style="color:{color}">● {name}</span>'
                      for name, color in COLORS.items())
    document = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HardiKhushi · Search performance</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f3f6fa;color:#17263b;
font:16px/1.6 system-ui,sans-serif}main{max-width:1180px;margin:auto;padding:36px 24px}
h1{font-size:clamp(1.8rem,4vw,2.8rem);line-height:1.2;margin:8px 0 16px}
h2{font-size:1.2rem;margin:0 0 12px}.eyebrow{color:#52657a;letter-spacing:.12em;
text-transform:uppercase;font-size:.8rem}.muted{color:#52657a}.legend{display:flex;
gap:24px;flex-wrap:wrap;margin:24px 0;font-weight:600}.grid{display:grid;
grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}.card{background:white;
border:1px solid #dbe3ed;border-radius:16px;padding:24px;margin-bottom:20px}
svg{display:block;width:100%;height:auto}svg text{font:13px system-ui;fill:#52657a}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;white-space:nowrap}
th,td{padding:10px 14px;text-align:right;border-bottom:1px solid #e5eaf0}
th:first-child,td:first-child{text-align:left}th{font-size:.82rem;color:#52657a}
a{color:#225bc2}footer{font-size:.85rem;overflow-wrap:anywhere}
@media(max-width:800px){.grid{grid-template-columns:1fr}.card{padding:16px}}
</style></head><body><main>
<div class="eyebrow">HardiKhushi · Algorithms in Finance</div>
<h1>Search performance</h1>
<p class="muted">Linear scans, binary search, and set lookups on the same query batches.</p>
<p class="muted"><strong>Preliminary snapshot.</strong> These saved results are from
the initial library-based implementation. Manual search procedures, version
comparisons, separate preparation/query timing, and raw repeats are still pending.
See <a href="PROGRESS.md">the progress log</a> for status and provenance.</p>
<div class="legend">__LEGEND__</div>
<div class="grid"><section class="card"><h2>Median batch time</h2>__TIME__</section>
<section class="card"><h2>Median peak allocation</h2>__MEMORY__</section></div>
<section class="card"><h2>Measured results</h2><div class="scroll"><table>
<thead><tr><th>Algorithm</th><th>Input IDs</th><th>Queries</th><th>Median ms</th>
<th>Min–max ms</th><th>Peak KiB</th></tr></thead><tbody>__ROWS__</tbody>
</table></div><p><a href="results/timing.csv">Download timing.csv</a> ·
<a href="results/memory.csv">Download memory.csv</a></p></section>
<section class="card"><h2>How to read these results</h2>
<p>Each measurement covers one complete query batch, including sorting or set
construction and the Boolean result list. Workload: __WORKLOAD__. Input generation and
correctness checks are excluded. Results are medians of __REPEATS__ repeats after
one warm-up per method and input size.</p>
<p>Memory is measured in separate runs using Python's tracemalloc. It reports peak
new traced allocations, including temporary data structures and results; it excludes
the already-created inputs and does not represent total process memory. Timing and
memory depend on the machine and Python version. Hover over chart points for values.</p>
</section><footer class="muted">Measured (UTC): __DATE__<br>Python __PYTHON__ · __PLATFORM__
<br>Seed: __SEED__. This page is a self-contained snapshot; rerun benchmark.py to refresh it.</footer>
</main></body></html>
'''
    replacements = {
        "__LEGEND__": legend,
        "__TIME__": chart(timing, "median_ms", "Median batch time", "ms"),
        "__MEMORY__": chart(memory, "median_peak_bytes", "Median peak allocation", "KiB", 1024),
        "__ROWS__": "".join(table_rows), "__REPEATS__": escape(first["repeats"]),
        "__DATE__": escape(first["measured_utc"]), "__PYTHON__": escape(first["python"]),
        "__PLATFORM__": escape(first["platform"]), "__SEED__": escape(first["seed"]),
        "__WORKLOAD__": escape(
            f'{first.get("scenario", "mixed")} queries; '
            f'hit rate {float(first.get("hit_rate", 0.5)):.1%}; '
            f'{first.get("duplicate_policy", "unique")} input IDs'
            + (" (settings from the original benchmark; older CSVs lack these columns)"
               if "scenario" not in first else "")
        ),
    }
    for token, value in replacements.items():
        document = document.replace(token, value)
    (directory / "dashboard.html").write_text(document, encoding="utf-8")


if __name__ == "__main__":
    generate_dashboard(Path(__file__).resolve().parent)

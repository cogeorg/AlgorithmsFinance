"""Create static timing charts and a summary from saved benchmark results."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # Save PNGs without a display or web server.
import matplotlib.pyplot as plt
import pandas as pd


HERE = Path(__file__).resolve().parent
TIMINGS = HERE / "results" / "timings.csv"
SUMMARY = HERE / "results" / "summary.csv"
CHARTS = HERE / "results" / "charts"

METHODS = {
    ("linear", "v1"): "Linear V1",
    ("binary", "v1"): "Binary V1",
    ("binary", "v2"): "Binary V2",
    ("hash", "v1"): "Hash V1",
}
SCENARIOS = {"present": "All present", "absent": "All absent", "mixed": "Mixed"}
MEASURES = {
    "total_seconds": ("total", "Total execution time"),
    "preparation_seconds": ("preparation", "Preparation time"),
    "query_seconds": ("query", "Query-batch time"),
}
SIZES = (1000, 10000, 100000)


def main():
    if not TIMINGS.is_file():
        raise SystemExit(f"Missing saved measurements: {TIMINGS}")

    results = pd.read_csv(TIMINGS)
    medians = results[results["row_type"] == "median"].copy()
    medians["method"] = [METHODS[(algorithm, version)]
                         for algorithm, version in zip(medians["algorithm"],
                                                       medians["version"])]
    if len(medians) != 72:
        raise ValueError("Expected 72 saved median rows (18 datasets x 4 methods)")

    for column in MEASURES:
        medians[column + "_ms"] = medians[column] * 1000

    summary = medians[["method", "n", "q", "scenario",
                       "preparation_seconds_ms", "query_seconds_ms",
                       "total_seconds_ms"]].rename(columns={
                           "method": "algorithm_version",
                           "preparation_seconds_ms": "median_preparation_ms",
                           "query_seconds_ms": "median_query_batch_ms",
                           "total_seconds_ms": "median_total_ms",
                       })
    summary = summary.sort_values(["q", "scenario", "n", "algorithm_version"])
    summary.to_csv(SUMMARY, index=False)

    CHARTS.mkdir(exist_ok=True)
    count = 0
    for q in (1, 100):
        for scenario, scenario_name in SCENARIOS.items():
            selected = medians[(medians["q"] == q) &
                               (medians["scenario"] == scenario)]
            if len(selected) != 12:
                raise ValueError(f"Missing median rows for q={q}, {scenario}")
            for column, (short_name, title) in MEASURES.items():
                fig, ax = plt.subplots(figsize=(8, 4.8))
                for method in METHODS.values():
                    values = selected[selected["method"] == method].sort_values("n")
                    if tuple(values["n"]) != SIZES:
                        raise ValueError(f"Missing input size for {method}, q={q}, {scenario}")
                    ax.plot(values["n"], values[column + "_ms"], marker="o",
                            label=method)
                ax.set_xscale("log", base=10)
                ax.set_xticks(SIZES, ["1,000", "10,000", "100,000"])
                ax.set_xlabel("Array size n (log scale)")
                ax.set_ylabel("Median execution time (ms)")
                ax.set_title(f"{title} - q={q}, {scenario_name}")
                ax.grid(True, alpha=0.3)
                ax.legend()
                fig.tight_layout()
                fig.savefig(CHARTS / f"q{q}_{scenario}_{short_name}.png", dpi=150)
                plt.close(fig)
                count += 1

    print(f"Saved {count} PNG charts to {CHARTS}")
    print(f"Saved {len(summary)} median rows to {SUMMARY}")


if __name__ == "__main__":
    main()

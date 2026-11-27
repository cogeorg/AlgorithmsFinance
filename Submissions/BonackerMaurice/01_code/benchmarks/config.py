"""Measurement grid, measurement definitions and run.json / CSV helpers."""
import csv
import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from datagen.generator import SCENARIOS, DatasetSpec
from search_algos import CURRENT, METHODS

PROJECT_DIR = Path(__file__).resolve().parent.parent       # Submissions/BonackerMaurice/01_code
SUBMISSION_DIR = PROJECT_DIR.parent                         # Submissions/BonackerMaurice
RESULTS_DIR = SUBMISSION_DIR / "02_results"
SEGMENTS = ("prepare", "query", "total")


@dataclass(frozen=True)
class Grid:
    sizes: tuple = (1_000, 10_000, 100_000)
    query_counts: tuple = (1, 100)
    scenarios: tuple = tuple(SCENARIOS)
    seed: int = 2026
    duplicate_policy: str = "allow"
    id_space_factor: int = 2
    repeats: int = 5
    min_measure_seconds: float = 0.01

    def specs(self) -> list:
        """All datasets. q=1 "mixed" is skipped: one query cannot be half present
        (it would round to all_present and duplicate that dataset exactly)."""
        return [DatasetSpec(n, q, s, self.seed, self.duplicate_policy, self.id_space_factor)
                for n in self.sizes for q in self.query_counts for s in self.scenarios
                if not (q == 1 and s == "mixed")]


QUICK = Grid(sizes=(100, 1_000), query_counts=(1, 10), repeats=3, min_measure_seconds=0.002)

DEFINITIONS = {
    "prepare": "One call of prepare(ids). linear v1: list copy; linear v2: no work "
               "(returns the input); binary: sorted() copy; hash: set() construction. "
               "Includes freeing the returned structure (each result is discarded inside "
               "the timed loop).",
    "query": "One complete batch of q queries, query(state, queries), on a state prepared "
             "freshly for each repeat outside the timed loop. Includes building the output list. "
             "Warm-cache, steady-state figure: within one measurement the same state and "
             "queries are reused calls_per_measurement times.",
    "total": "One prepare(ids) followed by one complete query batch, timed together "
             "(measured directly, not the sum of prepare and query). Every call builds a fresh "
             "structure and frees it, so total is generally not equal to prepare + query.",
    "elapsed_s": "Seconds per call: per prepare, per complete query batch, or per prepare+batch. "
                 "Each measurement runs the call calls_per_measurement times in a loop and divides "
                 "the elapsed time.perf_counter() time by that count. Per-query values "
                 "(query batch / q) are derived, not measured.",
    "repeats": "A calibration run (which is also the warm-up) picks calls_per_measurement, plus a "
               "25% margin, so one measurement lasts about >= min_measure_seconds; calls that "
               "already take that long run once. Actual duration of a measurement = "
               "elapsed_s * calls_per_measurement. Then `repeats` measurements per "
               "(dataset, method, version, segment); method order rotates each repeat. "
               "Report the median; all raw values are kept.",
    "datasets": "Grid n x q x scenario, except q=1 'mixed' (one query cannot be half present). "
                "Present queries are placed by first occurrence, evenly spread over the array "
                "(mean_first_hit_frac ~ 0.5), so linear-search hit costs are comparable across "
                "n and q. IDs are dense small ints (< 2^30): a best case for hashing and "
                "comparisons.",
    "gc": "Garbage collection is disabled inside timed loops (as timeit does); gc.collect() "
          "runs before each measurement.",
    "excluded": "Data generation, input validation, tests, correctness preflight checks, "
                "printing, memory tracing and dashboard rendering are outside timed regions.",
    "memory": "tracemalloc, in a separate process after timing. The input is built before tracing "
              "starts; each (dataset, method) gets a fresh tracing run. prepare_* is read after "
              "prepare(), total_* after the query batch, with state and output kept alive. "
              "Includes: the prepared structure, the output list, transient buffers (e.g. "
              "timsort's merge buffer, set resizing) in the peaks, and about 50-110 bytes of "
              "harness objects (see memory_baseline in run.json, not subtracted). Excludes: the "
              "input array and queries, and native allocations tracemalloc does not see. "
              "*_peak = highest traced bytes since tracing started; *_current = bytes still "
              "allocated then.",
    "noop_call_s": "Per-call overhead of the timing loop with the prepare/query wrapper "
                   "(functools.partial around a no-op); noop_lambda_call_s is the same for the "
                   "total segment's lambda. Not subtracted. Values within about 10x of these "
                   "are dominated by overhead.",
}


def write_run_config(run_dir, grid: Grid, run_id: str, **extra) -> dict:
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "run_id": run_id,
        "grid": {k: list(v) if isinstance(v, tuple) else v for k, v in asdict(grid).items()},
        "methods": [{"key": m.key, "method": m.method, "version": m.version, "role": m.role,
                     "label": m.label, "description": m.description} for m in METHODS],
        "current": dict(CURRENT),
        "segments": list(SEGMENTS),
        "units": "seconds (elapsed_s, median_s, min_s, max_s); bytes (memory)",
        "definitions": DEFINITIONS,
        "phases": {},
        **extra,
    }
    (run_dir / "run.json").write_text(json.dumps(config, indent=2) + "\n")
    return config


def load_run_config(run_dir):
    config = json.loads((Path(run_dir) / "run.json").read_text())
    names = {f.name for f in fields(Grid)}
    grid = Grid(**{k: tuple(v) if isinstance(v, list) else v
                   for k, v in config["grid"].items() if k in names})
    return config, grid


def update_run_config(run_dir, **updates) -> None:
    path = Path(run_dir) / "run.json"
    config = json.loads(path.read_text())
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(config.get(key), dict):
            config[key].update(value)
        else:
            config[key] = value
    path.write_text(json.dumps(config, indent=2) + "\n")


def write_csv(path, rows: list) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

"""Shared constants and helpers for the Phase 6 benchmarks (see README: "Benchmark limits")."""
from __future__ import annotations

import csv
import json
import math
import platform
import subprocess
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "generated"
RESULTS = ROOT / "results"

# Declared before any benchmark was run (README, commit 4ada71e).
LIMIT_SECONDS = 600          # per single replay, same for A and B
SLOW_FIRST_SECONDS = 60      # first replay slower than this -> one measurement only
TIMED_REPEATS = 5            # timed replays after the warm-up
A_MILLION_THRESHOLD = 60     # A needs a 100,000-event replay below this to run 1,000,000 events

SCENARIOS = ("buildup", "crowded", "mixed", "sweep", "cancel_churn")
GRID_SIZES = (1000, 10000, 100000)
GRID_SEEDS = (42, 43, 44)
CONCENTRATION_LEVELS = (4, 16, 64, 256, 1000, 4000)      # buildup, 100,000 events, seed 42


def stream_name(scenario: str, events: int, seed: int, levels: int = 1000) -> str:
    suffix = f"_L{levels}" if levels != 1000 else ""
    return f"{scenario}_{events}_s{seed}{suffix}.jsonl.gz"


def stream_path(scenario: str, events: int, seed: int, levels: int = 1000) -> Path:
    return DATA / stream_name(scenario, events, seed, levels)


def all_streams() -> list[dict]:
    """Every stream made by bench/make_data.sh, smallest first."""
    specs = [dict(scenario=s, events=m, seed=seed, levels=1000)
             for s in SCENARIOS for m in GRID_SIZES for seed in GRID_SEEDS]
    specs += [dict(scenario=s, events=1_000_000, seed=42, levels=1000) for s in SCENARIOS]
    specs += [dict(scenario="buildup", events=100000, seed=42, levels=n)
              for n in CONCENTRATION_LEVELS if n != 1000]
    return sorted(specs, key=lambda d: (d["events"], d["scenario"], d["seed"], d["levels"]))


def percentile_nearest_rank(sorted_values: list, p: float):
    """Nearest-rank percentile: the value at rank ceil(p/100 * n) of the sorted list (1-based)."""
    n = len(sorted_values)
    if n == 0:
        raise ValueError("no values")
    rank = max(1, math.ceil(p / 100 * n))
    return sorted_values[rank - 1]


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def append_csv(path: Path, fields: list[str], row: dict) -> None:
    path.parent.mkdir(exist_ok=True)
    new = not path.exists()
    with path.open("a", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if new:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in fields})


def run_result(rows: list[dict], version: str, scenario: str, seed: int, events: int,
               levels: int) -> dict | None:
    """The first row of one run in time_raw.csv (run-level fields: status, median_seconds, ...),
    or None if that run has no row yet."""
    key = (version, scenario, str(seed), str(events), str(levels))
    for row in rows:
        if (row["version"], row["scenario"], row["seed"], row["events"], row["levels"]) == key:
            return row
    return None


def _sh(*cmd: str) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:           # environment facts are best effort
        return ""


def power_state() -> dict:
    """Power source, battery percent and Low Power Mode of this Mac right now (best effort)."""
    batt = _sh("pmset", "-g", "batt")
    source = "unknown"
    if "'AC Power'" in batt:
        source = "ac"
    elif "'Battery Power'" in batt:
        source = "battery"
    percent = ""
    for token in batt.replace(";", " ").split():
        if token.endswith("%"):
            percent = token[:-1]
            break
    low = "unknown"
    for line in _sh("pmset", "-g").splitlines():
        if line.split()[:1] == ["lowpowermode"]:
            low = line.split()[1]
    return {"power_source": source, "battery_percent": percent, "low_power_mode": low}


def environment() -> dict:
    """Python, OS, machine, code version (git), dependencies, generator settings reference."""
    return {
        "python": platform.python_version(), "implementation": platform.python_implementation(),
        "zlib": zlib.ZLIB_VERSION, "platform": platform.platform(),
        "machine": platform.machine(), "processor": platform.processor(),
        "macos": _sh("sw_vers", "-productVersion"),
        "mac_model_id": _sh("sysctl", "-n", "hw.model"),
        "mac_hardware": [line.strip() for line in _sh("system_profiler", "SPHardwareDataType")
                         .splitlines() if line.strip().startswith(("Model Name", "Chip",
                                                                    "Total Number of Cores",
                                                                    "Memory"))],
        "cpu_brand": _sh("sysctl", "-n", "machdep.cpu.brand_string"),
        "memory_bytes": _sh("sysctl", "-n", "hw.memsize"),
        "power_at_start": power_state(),
        "git_commit": _sh("git", "-C", str(ROOT), "rev-parse", "HEAD"),
        "git_dirty": bool(_sh("git", "-C", str(ROOT), "status", "--porcelain", "--", ".")),
        "dependencies": _sh(sys.executable, "-m", "pip", "freeze").splitlines(),
        "constants": {"limit_seconds": LIMIT_SECONDS, "slow_first_seconds": SLOW_FIRST_SECONDS,
                      "timed_repeats": TIMED_REPEATS, "a_million_threshold": A_MILLION_THRESHOLD},
        "timing": "time.perf_counter around the replay loop; gc enabled (gc.collect() before each replay, outside the timed region)",
        "generator_settings": "results/generated_data_checksums.json",
    }


def write_environment() -> None:
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "env.json").write_text(json.dumps(environment(), indent=2) + "\n")

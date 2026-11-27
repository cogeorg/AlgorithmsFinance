"""Exploratory large-n timing run: the benchmark pipeline with a custom, larger grid.

    python -m explore.large_n                          # n = 100k, 1M, 10M (about 9 min)
    python -m explore.large_n 50000,500000,5000000     # any sizes, comma-separated

Not part of the slide grid. q = 10, scenarios all_absent and mixed, 3 repeats; the
memory phase is skipped (tracemalloc at 10M elements is slow and needs a lot of RAM).
Writes ../02_results/<stamp>_<sha>_large_quick/ with the same files as a normal run
except memory.csv; the dashboard lists it as a quick run. It reuses benchmarks.timing
unchanged, so the measured code and the timing protocol are the same as in the
official run. Close other heavy programs first; 10M needs about 2 GB of free RAM.
"""
import json
import subprocess
import sys
from datetime import datetime, timezone

from benchmarks.config import PROJECT_DIR, RESULTS_DIR, Grid, update_run_config, write_run_config
from benchmarks.environment import collect_environment, source_fingerprint

sizes = tuple(int(s) for s in sys.argv[1].split(",")) if len(sys.argv) > 1 else (
    100_000, 1_000_000, 10_000_000)
grid = Grid(sizes=sizes, query_counts=(10,), scenarios=("all_absent", "mixed"), repeats=3)
env = collect_environment(PROJECT_DIR)
stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
run_id = f"{stamp}_{env['git']['short'] or 'nogit'}_large_quick"
run_dir = RESULTS_DIR / run_id
run_dir.mkdir(parents=True)
(run_dir / "environment.json").write_text(json.dumps(env, indent=2) + "\n")
write_run_config(run_dir, grid, run_id, quick=True, status="running",
                 command=f"exploratory large-n run, sizes {sizes}")
print("run", run_id, flush=True)
proc = subprocess.run([sys.executable, "-m", "benchmarks.timing", str(run_dir)], cwd=PROJECT_DIR)
unchanged = source_fingerprint(PROJECT_DIR)["sha256"] == env["source"]["sha256"]
update_run_config(run_dir, status="complete" if proc.returncode == 0 else "aborted: timing failed",
                  source_unchanged=unchanged,
                  finished_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"))
print("done", run_dir, flush=True)

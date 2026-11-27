"""Run everything into ../02_results/<run_id>/: tests, then timing, then memory.

    python -m benchmarks.run            # full grid (AGENTS.md section 6), run from 01_code/
    python -m benchmarks.run --quick    # small grid for development (gitignored)

Timing and memory run as separate processes so that tracemalloc never overlaps
the timed code. Close other heavy programs before a full run.

run_id = <UTC timestamp>_<git short sha | nogit>[_dirty][_quick]
"""
import argparse
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from .config import (PROJECT_DIR, QUICK, RESULTS_DIR, SUBMISSION_DIR, Grid, update_run_config,
                     write_run_config)
from .environment import collect_environment, source_fingerprint


def redact(text: str) -> str:
    """Remove the home folder / user name (e.g. from failing tmp_path tests): public repo."""
    home = str(Path.home())
    for variant in {home, home.replace("\\", "/"), home.replace("\\", "\\\\")}:
        text = re.sub(re.escape(variant), "~", text, flags=re.IGNORECASE)
    return re.sub(r"pytest-of-[^\\/\s'\"]+", "pytest-of-<user>", text)


def run_tests(run_dir) -> dict:
    xml_path = run_dir / "tests.xml"
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", f"--junitxml={xml_path}"],
                          cwd=PROJECT_DIR, capture_output=True, text=True)
    (run_dir / "tests.txt").write_text(redact(proc.stdout + proc.stderr))
    if xml_path.exists():  # drop the machine's hostname and home paths from the public report
        tree = ET.parse(xml_path)
        for suite in tree.iter("testsuite"):
            suite.attrib.pop("hostname", None)
        tree.write(xml_path, encoding="utf-8", xml_declaration=True)
        xml_path.write_text(redact(xml_path.read_text(encoding="utf-8")), encoding="utf-8")
    lines = [ln for ln in proc.stdout.strip().splitlines() if ln.strip()]
    summary = lines[-1].strip("= ") if lines else ""
    counts = {k: int(v) for v, k in re.findall(r"(\d+) (passed|failed|skipped|errors?)", summary)}
    return {"exit_code": proc.returncode, "summary": summary, "counts": counts}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--quick", action="store_true", help="small grid for development")
    p.add_argument("--repeats", type=int)
    p.add_argument("--min-measure-seconds", type=float)
    p.add_argument("--seed", type=int)
    p.add_argument("--skip-tests", action="store_true")
    p.add_argument("--skip-memory", action="store_true")
    p.add_argument("--allow-test-failures", action="store_true")
    a = p.parse_args(argv)
    sys.stdout.reconfigure(line_buffering=True)  # keep output in order with the subprocesses

    grid = QUICK if a.quick else Grid()
    overrides = {"repeats": a.repeats, "min_measure_seconds": a.min_measure_seconds,
                 "seed": a.seed}
    grid = replace(grid, **{k: v for k, v in overrides.items() if v is not None})

    env = collect_environment(PROJECT_DIR)
    git = env["git"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_id = (f"{stamp}_{git['short'] or 'nogit'}" + ("_dirty" if git["dirty"] else "")
              + ("_quick" if a.quick else ""))
    run_dir = RESULTS_DIR / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "environment.json").write_text(json.dumps(env, indent=2) + "\n")
    write_run_config(run_dir, grid, run_id, quick=a.quick, status="running",
                     command="python -m benchmarks.run " + " ".join(argv or sys.argv[1:]))
    print(f"run {run_id}  (git {git['short']}, dirty={git['dirty']}, "
          f"source {env['source']['sha256'][:12]})")
    if git["dirty"]:
        print("WARNING: uncommitted changes; the commit hash does not identify the measured code.")
    elif git["dirty"] is None:
        print("WARNING: git status unavailable; code identity rests on source.sha256 only.")

    if not a.skip_tests:
        tests = run_tests(run_dir)
        update_run_config(run_dir, tests=tests)
        print(f"tests   {tests['summary']}")
        if tests["exit_code"] != 0 and not a.allow_test_failures:
            update_run_config(run_dir, status="aborted: tests failed")
            print("tests failed; not benchmarking (use --allow-test-failures to override)")
            return 1

    phases = ["timing"] + ([] if a.skip_memory else ["memory"])
    for phase in phases:
        proc = subprocess.run([sys.executable, "-m", f"benchmarks.{phase}", str(run_dir)],
                              cwd=PROJECT_DIR)
        if proc.returncode != 0:
            update_run_config(run_dir, status=f"aborted: {phase} failed")
            return proc.returncode

    unchanged = source_fingerprint(PROJECT_DIR)["sha256"] == env["source"]["sha256"]
    update_run_config(run_dir, status="complete", source_unchanged=unchanged,
                      finished_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    if not unchanged:
        print("WARNING: measured code changed during the run; do not use these results.")
    print(f"results in {run_dir.relative_to(SUBMISSION_DIR).as_posix()}")
    print("dashboard: python -m streamlit run dashboard/app.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())

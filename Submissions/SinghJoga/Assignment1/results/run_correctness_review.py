"""Run independent, hard-time-limited A/B checks for supplied workloads."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "correctness_review"
WORKER = ROOT / "results" / "check_supplied_stream_parity.py"
SCENARIOS = ("buildup", "crowded", "mixed", "sweep", "cancel_churn")
LIMIT_SECONDS = 60


def _read_progress(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    log_path = ROOT / "results" / "correctness_review_log.txt"
    started = time.perf_counter()
    records = []
    with log_path.open("w", encoding="utf-8") as log:
        log.write(
            "Exact command: .\\.venv\\Scripts\\python.exe "
            "results\\run_correctness_review.py\n"
        )
        log.write(
            "Per-stream enforced timeout: 60 seconds; one stream at a time.\n"
            "Worker compares ordered results, accepted sequence, canonical "
            "books, and invariants after every event.\n"
        )
        log.flush()
        for scenario in SCENARIOS:
            progress_path = OUT / f"{scenario}.json"
            stdout_path = OUT / f"{scenario}.stdout.txt"
            stderr_path = OUT / f"{scenario}.stderr.txt"
            command = [
                sys.executable,
                str(WORKER),
                "--scenario",
                scenario,
                "--progress",
                str(progress_path),
            ]
            one_started = time.perf_counter()
            status = "failed"
            return_code = None
            with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open(
                "w", encoding="utf-8"
            ) as stderr:
                process = subprocess.Popen(
                    command,
                    cwd=ROOT,
                    stdout=stdout,
                    stderr=stderr,
                    text=True,
                )
                try:
                    return_code = process.wait(timeout=LIMIT_SECONDS)
                    worker_state = _read_progress(progress_path)
                    status = (
                        "completed"
                        if return_code == 0 and worker_state.get("status") == "completed"
                        else "failed"
                    )
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    return_code = process.returncode
                    worker_state = _read_progress(progress_path)
                    status = "stopped_timeout"
            record = {
                "scenario": scenario,
                "status": status,
                "completed_events": worker_state.get("completed_events", 0),
                "target_events": 10000,
                "elapsed_seconds": round(time.perf_counter() - one_started, 3),
                "deadline_seconds": LIMIT_SECONDS,
                "worker_return_code": return_code,
                "progress_file": str(progress_path.relative_to(ROOT)),
                "stdout_file": str(stdout_path.relative_to(ROOT)),
                "stderr_file": str(stderr_path.relative_to(ROOT)),
            }
            records.append(record)
            log.write(json.dumps(record, sort_keys=True) + "\n")
            log.flush()
            print(json.dumps(record, sort_keys=True), flush=True)
    total = round(time.perf_counter() - started, 3)
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"Total elapsed seconds: {total}\n")
        log.write(f"Completed scenarios: {sum(r['status'] == 'completed' for r in records)}\n")
        log.write(f"Stopped scenarios: {sum(r['status'] == 'stopped_timeout' for r in records)}\n")
        log.write(f"Failed scenarios: {sum(r['status'] == 'failed' for r in records)}\n")
    return 0 if all(row["status"] in ("completed", "stopped_timeout") for row in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())

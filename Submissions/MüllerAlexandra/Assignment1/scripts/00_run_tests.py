"""Run pytest and preserve non-overwritten stage evidence."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
from time import perf_counter


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STAGE_PATTERN = re.compile(r"^[0-9]{2}_[a-z0-9_]+$")


def git_value(*args: str) -> str | None:
    """Return one Git value, or None when it is unavailable."""

    completed = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        required=True,
        help="Numbered evidence directory, for example 01_before_implementation",
    )
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Additional pytest arguments after --, for example -- -k baseline",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not STAGE_PATTERN.fullmatch(args.stage):
        raise SystemExit("stage must match NN_lowercase_words")

    pytest_args = list(args.pytest_args)
    if pytest_args[:1] == ["--"]:
        pytest_args = pytest_args[1:]

    output_dir = PROJECT_ROOT / "evidence" / args.stage
    log_path = output_dir / "test_run.log"
    metadata_path = output_dir / "test_run.json"
    if log_path.exists() or metadata_path.exists():
        raise SystemExit(f"refusing to overwrite existing evidence in {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "-m",
        "pytest",
        "-p",
        "no:cacheprovider",
        *pytest_args,
    ]
    started = datetime.now(timezone.utc)
    start_clock = perf_counter()
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    elapsed = perf_counter() - start_clock
    finished = datetime.now(timezone.utc)

    branch = git_value("branch", "--show-current")
    head = git_value("rev-parse", "HEAD")
    status = git_value("status", "--short")
    metadata = {
        "schema_version": 1,
        "stage": args.stage,
        "command": command,
        "working_directory": ".",
        "started_utc": started.isoformat(),
        "finished_utc": finished.isoformat(),
        "elapsed_seconds": elapsed,
        "exit_code": completed.returncode,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "pytest_version": importlib.metadata.version("pytest"),
        "platform": platform.platform(),
        "git": {
            "branch": branch,
            "head": head,
            "status_before_evidence_files": status,
            "clean_before_evidence_files": status == "",
        },
    }
    header = [
        f"stage: {args.stage}",
        f"started_utc: {metadata['started_utc']}",
        f"finished_utc: {metadata['finished_utc']}",
        f"elapsed_seconds: {elapsed:.6f}",
        f"exit_code: {completed.returncode}",
        f"python_version: {metadata['python_version']}",
        f"pytest_version: {metadata['pytest_version']}",
        f"git_branch: {branch}",
        f"git_head: {head}",
        "command: " + subprocess.list2cmdline(command),
    ]
    log_text = "\n".join(header) + "\n\n=== stdout ===\n"
    log_text += completed.stdout
    log_text += "\n=== stderr ===\n"
    log_text += completed.stderr
    log_path.write_text(log_text, encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    sys.stdout.write(completed.stdout)
    sys.stderr.write(completed.stderr)
    print(f"Evidence saved in {output_dir}")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())


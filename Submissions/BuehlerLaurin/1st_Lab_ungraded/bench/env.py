"""Environment and code-version metadata saved next to every measurement (LAB_SPEC.md I6).

Specification
-------------
``collect_env() -> dict``

Output keys
    timestamp_utc       ISO 8601 time of collection.
    python_version      e.g. "3.13.15"; python_implementation e.g. "CPython".
    platform, machine, processor, cpu_count   from ``platform`` and ``os``.
    git_commit          ``git rev-parse HEAD`` of the repository, or None if git fails.
    git_dirty           True if ``git status --porcelain`` reports any change (the
                        measured code may differ from the commit), None if git fails.
    git_dirty_files     Number of changed/untracked paths reported by git.

Only read-only git commands are used (AGENTS.md section 1).
Not timed: called before/after measurements, never inside a timed region.
"""

from __future__ import annotations

import datetime as _dt
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

SUBMISSION_DIR = Path(__file__).resolve().parent.parent


def _git(*args: str) -> str | None:
    """Run a read-only git command in the submission folder; None on any failure."""
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=SUBMISSION_DIR,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout


def collect_env() -> dict[str, Any]:
    """Return a JSON-serializable description of machine, Python and code version."""
    commit = _git("rev-parse", "HEAD")
    status = _git("status", "--porcelain")
    changed = [line for line in status.splitlines() if line.strip()] if status is not None else None
    return {
        "timestamp_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "git_commit": commit.strip() if commit else None,
        "git_dirty": (len(changed) > 0) if changed is not None else None,
        "git_dirty_files": len(changed) if changed is not None else None,
    }

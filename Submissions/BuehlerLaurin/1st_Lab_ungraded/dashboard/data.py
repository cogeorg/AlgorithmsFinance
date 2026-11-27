"""Load saved measurement results for the dashboard (LAB_SPEC.md D4, D5).

Reads only files written by ``bench/timing.py`` and ``bench/memory.py``. It never runs a
benchmark and never imports the algorithms.

Specification
-------------
``list_runs(kind)``  kind "timing" or "memory" -> list[RunInfo], newest first.
    A run is identified by its ``<kind>_<stamp>_env.json`` file; its raw and summary CSV
    files sit next to it. Runs with missing files are skipped.
``default_run(runs)`` -> the newest run with ``git_dirty == False``, else the newest run,
    else None (no results saved yet).
``load_run(run)`` -> (summary DataFrame, raw DataFrame, env-file dict).
``speedup_table(summary, metric)`` -> original median / revised median per method, n, q,
    hit rate. Values > 1 mean the revised version is faster.

Units: timing values in seconds, memory values in bytes (as saved).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
KIND_DIRS = {"timing": RESULTS_DIR / "raw", "memory": RESULTS_DIR / "memory"}


@dataclass(frozen=True)
class RunInfo:
    """One saved measurement run."""

    kind: str
    stamp: str
    env_path: Path
    raw_path: Path
    summary_path: Path
    git_commit: str | None
    git_dirty: bool | None

    @property
    def label(self) -> str:
        commit = (self.git_commit or "unknown")[:7]
        state = {False: "clean", True: "DIRTY (uncommitted code)", None: "unknown"}[self.git_dirty]
        return f"{self.stamp} | commit {commit} | {state}"


def list_runs(kind: str, results_dir: Path | None = None) -> list[RunInfo]:
    """All complete runs of one kind, newest first."""
    if kind not in KIND_DIRS:
        raise ValueError(f"kind must be one of {sorted(KIND_DIRS)}")
    folder = KIND_DIRS[kind] if results_dir is None else results_dir
    runs: list[RunInfo] = []
    for env_path in sorted(folder.glob(f"{kind}_*_env.json"), reverse=True):
        base = env_path.name.removesuffix("_env.json")
        raw_path = env_path.with_name(f"{base}.csv")
        summary_path = env_path.with_name(f"{base}_summary.csv")
        if not (raw_path.exists() and summary_path.exists()):
            continue
        env = json.loads(env_path.read_text(encoding="utf-8")).get("env", {})
        runs.append(
            RunInfo(
                kind=kind,
                stamp=base.removeprefix(f"{kind}_"),
                env_path=env_path,
                raw_path=raw_path,
                summary_path=summary_path,
                git_commit=env.get("git_commit"),
                git_dirty=env.get("git_dirty"),
            )
        )
    return runs


def default_run(runs: list[RunInfo]) -> RunInfo | None:
    """Newest clean run, else newest run, else None."""
    for run in runs:
        if run.git_dirty is False:
            return run
    return runs[0] if runs else None


def load_run(run: RunInfo) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Read summary CSV, raw CSV and the env JSON of one run."""
    summary = pd.read_csv(run.summary_path)
    raw = pd.read_csv(run.raw_path)
    env_file = json.loads(run.env_path.read_text(encoding="utf-8"))
    return summary, raw, env_file


def speedup_table(summary: pd.DataFrame, metric: str) -> pd.DataFrame:
    """original / revised ratio of the median ``metric`` (e.g. "total_s") per cell."""
    column = f"{metric}_median"
    wide = summary.pivot_table(
        index=["method", "n", "q", "hit_rate"], columns="version", values=column
    ).reset_index()
    wide["speedup_original_over_revised"] = wide["original"] / wide["revised"]
    return wide.rename(
        columns={"original": f"original_{column}", "revised": f"revised_{column}"}
    )

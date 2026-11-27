"""Smoke tests for the measurement code (bench/timing.py, bench/memory.py, bench/env.py).

They run a tiny grid into a temporary folder and check the saved files: required columns,
units, positive times, one row per repeat, identical inputs for every method, and
the environment record. They do not check how fast anything is.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from bench import memory, timing
from bench.env import collect_env
from membership import METHODS, MethodSpec


@pytest.fixture
def tiny_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    monkeypatch.setattr(timing, "MIN_TIMED_SECONDS", 0.0)  # k = 1, keeps the test fast
    return timing.run_grid(
        n_values=[50], q_values=[1, 10], hit_rates=[1.0, 0.0], repeats=2, out_dir=tmp_path
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_raw_rows_cover_grid_methods_and_repeats(tiny_run: dict[str, Path]) -> None:
    rows = read_csv(tiny_run["raw"])
    assert len(rows) == 1 * 2 * 2 * len(METHODS) * 2  # n x q x hit x methods x repeats
    for row in rows:
        assert row["unit"] == "seconds"
        for field in ("prep_s", "query_batch_s", "total_s", "prep_plus_query_s"):
            assert float(row[field]) > 0
        for field in ("k_prep", "k_query", "k_total"):
            assert int(row[field]) >= 1
        assert row["seed"] == str(timing.SEED)
        assert row["duplicate_policy"] == "allow"


def test_summary_has_one_row_per_cell_and_method(tiny_run: dict[str, Path]) -> None:
    rows = read_csv(tiny_run["summary"])
    assert len(rows) == 1 * 2 * 2 * len(METHODS)
    assert all(int(r["repeats"]) == 2 for r in rows)
    for r in rows:
        assert float(r["total_s_min"]) <= float(r["total_s_median"]) <= float(r["total_s_max"])


def test_env_file_records_settings_cases_and_code_version(tiny_run: dict[str, Path]) -> None:
    data = json.loads(tiny_run["env"].read_text(encoding="utf-8"))
    assert data["settings"]["unit"] == "seconds"
    assert data["settings"]["repeats"] == 2
    assert len(data["cases"]) == 4
    for key in ("python_version", "platform", "git_commit", "git_dirty", "timestamp_utc"):
        assert key in data["env"]


def test_wrong_method_is_detected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The oracle check after timing must reject a method that returns wrong answers."""
    monkeypatch.setattr(timing, "MIN_TIMED_SECONDS", 0.0)
    broken = MethodSpec("broken", "x", lambda ids: ids, lambda s, qs: [False] * len(qs))
    with pytest.raises(AssertionError):
        timing.run_grid(
            n_values=[10], q_values=[5], hit_rates=[1.0], methods=[broken],
            repeats=1, out_dir=tmp_path,
        )


@pytest.fixture
def tiny_memory_run(tmp_path: Path) -> dict[str, Path]:
    return memory.run_grid(
        n_values=[1_000], q_values=[1, 100], hit_rates=[0.5], repeats=1, out_dir=tmp_path
    )


def test_memory_rows_have_flags_units_and_cover_all_phases(
    tiny_memory_run: dict[str, Path],
) -> None:
    rows = read_csv(tiny_memory_run["raw"])
    assert len(rows) == 1 * 2 * 1 * len(METHODS) * 3  # n x q x hit x methods x phases
    expected_flags = {
        "prepare": ("False", "True", "False"),
        "query": ("False", "False", "True"),
        "total": ("False", "True", "True"),
    }
    for row in rows:
        assert row["unit"] == "bytes" and row["tool"] == "tracemalloc"
        flags = (row["includes_input"], row["includes_prepared"], row["includes_output"])
        assert flags == expected_flags[row["phase"]]
        assert int(row["peak_bytes"]) >= int(row["current_bytes"]) >= 0


def test_memory_values_are_plausible(tiny_memory_run: dict[str, Path]) -> None:
    """Rough sanity bounds only (n = 1,000): linear prepares nothing, a sorted copy holds
    n references (>= 8n bytes), the hash set is larger than n references."""
    rows = read_csv(tiny_memory_run["raw"])

    def current(label: str, phase: str, q: int) -> int:
        (row,) = [r for r in rows if r["label"] == label and r["phase"] == phase
                  and int(r["q"]) == q]
        return int(row["current_bytes"])

    assert current("linear-original", "prepare", 100) < 1_000
    assert current("binary-original", "prepare", 100) >= 8 * 1_000
    assert current("hash-original", "prepare", 100) > 8 * 1_000
    assert current("hash-original", "query", 100) >= 8 * 100  # output list kept alive

    linear_prep = [r for r in rows if r["method"] == "linear" and r["phase"] == "prepare"]
    assert all(r["state_is_input"] == "True" for r in linear_prep)
    binary_prep = [r for r in rows if r["method"] == "binary" and r["phase"] == "prepare"]
    assert all(r["state_is_input"] == "False" for r in binary_prep)


def test_collect_env_is_json_serializable() -> None:
    env = collect_env()
    json.dumps(env)
    assert env["python_version"].count(".") == 2

#!/usr/bin/env python3
"""Reproduce Ben Lavi's audit evidence for WelscherYannick.

Run with a Python environment containing the audited submission's pinned
requirements:

    python reproduce_audit.py /path/to/Submissions/WelscherYannick

The target checkout is read-only. Dashboard mutation probes use a temporary
copy that is deleted automatically.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path


EXPECTED_COMMIT = "654516b585dd419ff63f37642d5c211891799fcb"
SCENARIO_FIELDS = (
    "n",
    "q",
    "hit_rate_target",
    "hit_rate_actual",
    "duplicate_rate",
    "seed",
)
TIME_COLUMNS = ("prepare_s", "query_batch_s", "total_s")
MEMORY_COLUMNS = (
    "prepare_current_B",
    "prepare_peak_B",
    "query_current_B",
    "query_peak_B",
    "total_current_B",
    "total_peak_B",
    "output_getsizeof_B",
)


def target_commit(target: Path) -> str:
    repository = target.parents[1]
    return subprocess.check_output(
        ("git", "-C", str(repository), "rev-parse", "HEAD"),
        text=True,
    ).strip()


def dashboard_probes(target: Path) -> None:
    """Reproduce cache, filter, and visible-memory-column behavior in /tmp."""

    import pandas as pd
    from streamlit.testing.v1 import AppTest

    with tempfile.TemporaryDirectory(prefix="yannick-dashboard-audit-") as temp:
        copied = Path(temp) / "WelscherYannick"
        shutil.copytree(target, copied)
        app = AppTest.from_file(str(copied / "dashboard" / "app.py"), default_timeout=60)
        app.run()
        assert not app.exception

        timing_table = next(
            frame.value for frame in app.dataframe if "prepare_s" in frame.value.columns
        )
        before = float(timing_table.iloc[0]["prepare_s"])
        timing_path = copied / "results" / "timing_raw.csv"
        raw = pd.read_csv(timing_path)
        raw.loc[0, "prepare_s"] = 123.456789
        raw.to_csv(timing_path, index=False)
        app.run()
        assert not app.exception
        timing_table = next(
            frame.value for frame in app.dataframe if "prepare_s" in frame.value.columns
        )
        after = float(timing_table.iloc[0]["prepare_s"])
        assert after == before, "expected to reproduce stale cached dashboard data"

        app.segmented_control(key="versions").set_value(["v1"]).run()
        assert not app.exception
        chart_specs = [json.loads(chart.proto.spec) for chart in app.get("plotly_chart")]
        revision_names = None
        for spec in chart_specs:
            names = [trace.get("name") for trace in spec.get("data", [])]
            if names == ["v2 (iterative)", "v3 (lower bound)"]:
                revision_names = names
                break
        assert revision_names is not None, "revision overview unexpectedly followed v1-only filter"

        memory_table = next(
            frame.value
            for frame in app.dataframe
            if "prepare current" in frame.value.columns
        )
        visible = list(memory_table.columns)
        assert "total current" not in visible
        assert "output getsizeof" not in visible

        print(
            "Dashboard cache reproduced: file changed "
            f"{before:.12g} -> 123.456789; rerender still showed {after:.12g}"
        )
        print(
            "Version-filter inconsistency reproduced: selected ['v1']; "
            f"revision overview still showed {revision_names}"
        )
        print(f"Visible memory-table columns: {visible}")


def algorithm_probes(target: Path) -> None:
    """Run literal-answer cases independent of the supplied test helpers."""

    sys.path.insert(0, str(target / "src"))
    from registry import VERSIONS

    cases = (
        ("both empty", [], [], []),
        ("empty ids", [], [0, -1, 9], [False, False, False]),
        ("empty queries", [3, 1, 3], [], []),
        (
            "duplicates unsorted",
            [7, 11, 7, 5, 11],
            [11, 9, 7, 5],
            [True, False, True, True],
        ),
        (
            "first last absent",
            [40, 10, 30, 20],
            [40, 20, 5, 50, 30],
            [True, True, False, False, True],
        ),
        (
            "repeated queries",
            [2, 4, 6],
            [6, 1, 6, 2, 1, 4],
            [True, False, True, True, False, True],
        ),
    )

    assertions = 0
    pairs = 0
    for version, methods in VERSIONS.items():
        for method_name, method in methods.items():
            pairs += 1
            label = f"{version}/{method_name}"
            for case_name, ids, queries, expected in cases:
                ids_before, queries_before = deepcopy(ids), deepcopy(queries)
                actual = method.contains_all(ids, queries)
                assert actual == expected, (label, case_name, actual, expected)
                assert ids == ids_before and queries == queries_before
                assert type(actual) is list
                assert all(type(item) is bool for item in actual)
                assertions += 1

            ids = [8, 3, 8, 1]
            state = method.prepare(ids)
            state_before = deepcopy(state)
            first = method.query(state, [1, 9, 8])
            assert first == [True, False, True]
            assert method.query(state, [8, 8, 2]) == [True, True, False]
            assert method.query(state, [1, 9, 8]) == first
            assert state == state_before
            ids[:] = [99]
            assert method.query(state, [99, 8, 3]) == [False, True, True]
            assertions += 4

    print(
        f"Independent algorithm assertions passed: {assertions} "
        f"across {pairs} method/version pairs"
    )


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        return list(csv.DictReader(source))


def scenario_signatures(rows: list[dict[str, str]]) -> dict[int, set[tuple[str, ...]]]:
    signatures: dict[int, set[tuple[str, ...]]] = defaultdict(set)
    for row in rows:
        signatures[int(row["scenario"])].add(tuple(row[key] for key in SCENARIO_FIELDS))
    return signatures


def raw_and_dashboard_checks(target: Path) -> None:
    """Check schemas, units, inputs, raw aggregates, and the timing anomaly."""

    results = target / "results"
    timing = load_csv(results / "timing_raw.csv")
    memory = load_csv(results / "memory_raw.csv")
    timing_meta = json.loads((results / "timing_metadata.json").read_text())
    memory_meta = json.loads((results / "memory_metadata.json").read_text())

    assert len(timing) == 675
    assert len(memory) == 405
    assert all(unit == "bytes" for unit in memory_meta["units"].values())
    assert timing_meta["units"] == {
        "prepare_s": "seconds per prepare(ids) call",
        "query_batch_s": (
            "seconds per query(state, queries) call for the whole batch of q queries"
        ),
        "total_s": "seconds per prepare + query call, timed together",
    }

    timing_signatures = scenario_signatures(timing)
    memory_signatures = scenario_signatures(memory)
    assert len(timing_signatures) == len(memory_signatures) == 15
    assert all(len(values) == 1 for values in timing_signatures.values())
    assert timing_signatures == memory_signatures
    assert set(
        Counter((row["scenario"], row["version"], row["method"]) for row in timing).values()
    ) == {5}
    assert set(
        Counter((row["scenario"], row["version"], row["method"]) for row in memory).values()
    ) == {3}

    timing_groups: dict[tuple[int, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in timing:
        timing_groups[(int(row["scenario"]), row["version"], row["method"])].append(row)
    memory_groups: dict[tuple[int, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in memory:
        memory_groups[(int(row["scenario"]), row["version"], row["method"])].append(row)

    sys.modules.pop("data", None)
    sys.path.insert(0, str(target / "dashboard"))
    import data as dashboard_data

    timing_summary = dashboard_data.timing_summary(
        dashboard_data.load_timing(results)
    ).set_index(["scenario", "version", "method"])
    for key, rows in timing_groups.items():
        for column in TIME_COLUMNS:
            values = [float(row[column]) for row in rows]
            assert timing_summary.loc[key, f"{column}_median"] == statistics.median(values)
            assert timing_summary.loc[key, f"{column}_min"] == min(values)
            assert timing_summary.loc[key, f"{column}_max"] == max(values)

    memory_summary = dashboard_data.memory_summary(
        dashboard_data.load_memory(results)
    ).set_index(["scenario", "version", "method"])
    for key, rows in memory_groups.items():
        for column in MEMORY_COLUMNS:
            values = [int(row[column]) for row in rows]
            assert memory_summary.loc[key, column] == statistics.median(values)

    raw_total_below = sum(
        float(row["total_s"]) < float(row["prepare_s"]) for row in timing
    )
    median_total_below = []
    for key, rows in timing_groups.items():
        preparation = statistics.median(float(row["prepare_s"]) for row in rows)
        total = statistics.median(float(row["total_s"]) for row in rows)
        if total < preparation:
            median_total_below.append(
                (key, preparation, total, (preparation - total) / preparation)
            )
    worst = max(median_total_below, key=lambda item: item[3])

    print("Raw schemas, units, and timing/memory input consistency: OK")
    print("Dashboard aggregates matched all committed raw groups")
    print(f"Raw rows with total < preparation: {raw_total_below}/{len(timing)}")
    print(
        "Median groups with total < preparation: "
        f"{len(median_total_below)}/{len(timing_groups)}"
    )
    print(
        f"Worst median gap: {worst[0]}, preparation={worst[1]:.9g}s, "
        f"total={worst[2]:.9g}s, below by {worst[3]:.1%}"
    )


def audit_commit_check(target: Path) -> None:
    readme = (target / "README.md").read_text()
    section = readme.split("## Commit for the audit", 1)[1]
    shas = re.findall(r"\b[0-9a-f]{40}\b", section)
    assert "placeholder" in section.lower()
    assert not shas
    print("Audit-target omission reproduced: section is a placeholder with no full SHA")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path, help="path to Submissions/WelscherYannick")
    arguments = parser.parse_args()
    target = arguments.target.resolve()
    if not (target / "src" / "registry.py").is_file():
        parser.error(f"not a WelscherYannick submission: {target}")

    actual_commit = target_commit(target)
    assert actual_commit == EXPECTED_COMMIT, (
        f"expected {EXPECTED_COMMIT}, found {actual_commit}"
    )
    print(f"Verified audited commit: {actual_commit}")

    dashboard_probes(target)
    algorithm_probes(target)
    raw_and_dashboard_checks(target)
    audit_commit_check(target)
    print("All audit reproductions completed successfully")


if __name__ == "__main__":
    main()

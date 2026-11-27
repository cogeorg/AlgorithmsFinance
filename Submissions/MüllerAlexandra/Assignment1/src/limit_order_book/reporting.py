"""Aggregate saved experiment records without rerunning measurements."""

from __future__ import annotations

from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path
from typing import Any


JsonObject = dict[str, Any]


def _read_json(path: Path) -> JsonObject:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            return json.load(stream)
    return json.loads(path.read_text(encoding="utf-8"))


def _status_paths(results_root: Path) -> list[tuple[str, Path]]:
    paths: list[tuple[str, Path]] = []
    formal = results_root / "status"
    extension = results_root / "extension_1m" / "status"
    if formal.is_dir():
        paths.extend(("formal", path) for path in formal.rglob("*.json"))
    if extension.is_dir():
        paths.extend(("extension_1m", path) for path in extension.rglob("*.json"))
    return sorted(paths, key=lambda item: str(item[1]))


def _status_row(group: str, document: JsonObject) -> JsonObject:
    task = document["task"]
    environment = document.get("environment", {})
    git = environment.get("git", {})
    return {
        "experiment_group": group,
        "task_id": document["task_id"],
        "version": task["version"],
        "phase": task["phase"],
        "scenario": task["scenario"],
        "event_count": task["event_count"],
        "seed": task["seed"],
        "levels": task["levels"],
        "outcome": document["outcome"],
        "timeout_seconds": document.get("timeout_seconds"),
        "elapsed_seconds": document.get("elapsed_seconds"),
        "stopping_reason": document.get("stopping_reason"),
        "result_path": document.get("result_path"),
        "python_version": environment.get("python_version"),
        "platform": environment.get("platform"),
        "git_commit": git.get("commit"),
        "code_dirty": git.get("code_dirty"),
    }


def _identity(group: str, task: JsonObject, version: str) -> JsonObject:
    return {
        "experiment_group": group,
        "version": version,
        "scenario": task["scenario"],
        "event_count": task["event_count"],
        "seed": task["seed"],
        "levels": task["levels"],
    }


def _collect_completed_result(
    *,
    project_root: Path,
    group: str,
    status: JsonObject,
    data: JsonObject,
) -> None:
    task = status["task"]
    result_path = status.get("result_path")
    if not result_path:
        raise ValueError(f"completed task lacks result path: {status['task_id']}")
    result = _read_json(project_root / str(result_path))
    phase = task["phase"]
    identity = _identity(group, task, result["version"])

    if phase == "throughput":
        summary = {**identity, **result["summary"]}
        summary["parse_seconds"] = result["input"]["parse_seconds"]
        data["throughput_summaries"].append(summary)
        for record in result["records"]:
            data["throughput_repeats"].append({**identity, **record})
        return

    if phase == "latency":
        summary = result["summary"]
        scopes = {
            "overall": summary["overall"],
            "early_10_percent": summary["early_10_percent"],
            "late_10_percent": summary["late_10_percent"],
        }
        scopes.update(
            {f"event_type:{name}": values for name, values in summary["by_event_type"].items()}
        )
        for scope, values in scopes.items():
            data["latency_summaries"].append(
                {**identity, "scope": scope, **values}
            )
        return

    if phase in {"memory_state", "memory_retained_output"}:
        measurement = result["measurement"]
        mode = measurement["mode"]
        data["memory_finals"].append(
            {**identity, "mode": mode, **measurement["final"]}
        )
        for checkpoint in measurement["checkpoints"]:
            data["memory_checkpoints"].append(
                {**identity, "mode": mode, **checkpoint}
            )
        return

    raise ValueError(f"unsupported completed phase: {phase}")


def _throughput_comparisons(summaries: list[JsonObject]) -> list[JsonObject]:
    keys = ("experiment_group", "scenario", "event_count", "seed", "levels")
    paired: dict[tuple[object, ...], dict[str, JsonObject]] = defaultdict(dict)
    for row in summaries:
        paired[tuple(row[key] for key in keys)][row["version"]] = row

    comparisons: list[JsonObject] = []
    for key, versions in sorted(paired.items()):
        if set(versions) != {"baseline", "revised"}:
            continue
        baseline = versions["baseline"]["median_throughput_events_per_second"]
        revised = versions["revised"]["median_throughput_events_per_second"]
        comparisons.append(
            {
                **dict(zip(keys, key, strict=True)),
                "baseline_events_per_second": baseline,
                "revised_events_per_second": revised,
                "speedup_revised_over_baseline": revised / baseline,
            }
        )
    return comparisons


def _collect_stress(results_root: Path, data: JsonObject) -> None:
    stress_root = results_root / "stress"
    if not stress_root.is_dir():
        return
    for path in sorted(stress_root.rglob("*.json.gz")):
        document = _read_json(path)
        version = document["version"]
        settings = document["settings"]
        for record in document["liquidation_timing"]["records"]:
            data["liquidation_repeats"].append(
                {"version": version, **record}
            )
        for sale_size, summary in document["liquidation_timing"]["summaries"].items():
            data["liquidation_summaries"].append(
                {"version": version, "sale_size": sale_size, **summary}
            )
        for record in document["liquidation_memory"]:
            data["liquidation_memory"].append({"version": version, **record})
        for diagnostic in document["diagnostics"]:
            counts = diagnostic["counts"]
            data["diagnostics"].append(
                {
                    "version": version,
                    "scenario": diagnostic["scenario"],
                    "seed": diagnostic["seed"],
                    "parse_seconds": diagnostic["input"]["parse_seconds"],
                    **{
                        key: value
                        for key, value in counts.items()
                        if key != "event_type_counts"
                    },
                    "limit_events": counts["event_type_counts"].get("LIMIT", 0),
                    "cancel_events": counts["event_type_counts"].get("CANCEL", 0),
                    "market_sell_events": counts["event_type_counts"].get(
                        "MARKET_SELL", 0
                    ),
                }
            )
        data["stress_settings"].append({"version": version, **settings})


def collect_dashboard_data(results_root: Path) -> JsonObject:
    """Load saved results and return dashboard-ready JSON-compatible tables."""
    results_root = results_root.resolve()
    project_root = results_root.parent
    data: JsonObject = {
        "schema_version": 1,
        "statuses": [],
        "status_counts": {},
        "throughput_repeats": [],
        "throughput_summaries": [],
        "throughput_comparisons": [],
        "latency_summaries": [],
        "memory_finals": [],
        "memory_checkpoints": [],
        "liquidation_repeats": [],
        "liquidation_summaries": [],
        "liquidation_memory": [],
        "diagnostics": [],
        "stress_settings": [],
    }
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for group, path in _status_paths(results_root):
        document = _read_json(path)
        row = _status_row(group, document)
        data["statuses"].append(row)
        counts[row["version"]][row["outcome"]] += 1
        if row["outcome"] == "completed":
            _collect_completed_result(
                project_root=project_root,
                group=group,
                status=document,
                data=data,
            )

    data["status_counts"] = {
        version: dict(sorted(outcomes.items()))
        for version, outcomes in sorted(counts.items())
    }
    data["throughput_comparisons"] = _throughput_comparisons(
        data["throughput_summaries"]
    )
    _collect_stress(results_root, data)
    return data


def write_dashboard_data(results_root: Path, output_path: Path) -> None:
    """Write one exclusive gzip JSON dashboard artifact."""
    if output_path.exists():
        raise FileExistsError(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = collect_dashboard_data(results_root)
    with gzip.open(output_path, "xt", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")

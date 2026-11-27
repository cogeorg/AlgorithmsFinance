"""Read-only loaders and coverage reconciliation for saved benchmark evidence."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "benchmarks"


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _status(value: Any) -> str:
    if value in ("completed", "reused", "reusable"):
        return "completed"
    if value in ("interrupted", "in_progress"):
        return "interrupted"
    if value in ("stopped_timeout", "stopped_memory_limit", "stopped_before_start",
                 "stopped_error", "error", "failed"):
        return "stopped"
    return str(value or "never_attempted")


def _phase_policy(run_dir: Path, phase: str, data: dict[str, Any]) -> str:
    if data.get("record_type") != "phase_attempt":
        return f"aggregate-{data.get('time_limit_seconds')}s"
    primary = {
        "input_read_parse", "empty_engine_construction", "engine_replay",
        "total_application", "initial_book_construction",
        "sell_operation_10pct", "sell_operation_100pct", "sell_operation_200pct",
        "total_application_sell_10pct", "total_application_sell_100pct",
        "total_application_sell_200pct",
    }
    category = "primary" if phase in primary else phase
    metadata = _read_json(run_dir / "metadata.json") or {}
    settings = metadata.get("settings", {})
    manifest = _read_json(run_dir / "CONTINUATION_STOP_20261126.json") or {}
    limits = settings.get("phase_budgets", {}) or manifest.get("phase_limits_seconds", {})
    budget = limits.get(category)
    if budget is None:
        budget = data.get("phase_budget_seconds", data.get("time_limit_seconds"))
    return f"phase-{category}-{budget:g}s" if isinstance(budget, (int, float)) else f"phase-{category}"


def load_saved_rows() -> list[dict[str, Any]]:
    """Load actual measurement rows; configuration summaries are not counted twice."""
    rows: list[dict[str, Any]] = []
    for run_dir in sorted(p for p in RESULTS.iterdir() if p.is_dir()):
        if not (run_dir / "metadata.json").exists():
            continue
        plans = sorted((run_dir / "continuation_plans").glob("*.json"))
        plan = _read_json(plans[-1]) if plans else None
        continuation_statuses: dict[tuple[str, str], str] = {}
        for config in (plan or {}).get("configs", []):
            for phase_info in config.get("phases", []):
                continuation_statuses[(config.get("config_id", ""), phase_info.get("phase", ""))] = (
                    phase_info.get("status", "")
                )
        for path in sorted((run_dir / "records").glob("*__attempt_*.json")):
            data = _read_json(path)
            if not data or data.get("record_type") == "configuration_attempt":
                continue
            case = data.get("case", {})
            config_id = data.get("config_id", "")
            version = data.get("version") or config_id.rsplit("__", 1)[-1]
            phase_job = data.get("phase_job")
            for item in data.get("rows", []):
                phase = phase_job or item.get("measurement_phase") or item.get("phase")
                if not phase:
                    continue
                if phase.endswith("_summary"):
                    phase = phase.removesuffix("_summary")
                rows.append({
                    **item,
                    "run_id": run_dir.name,
                    "config_id": config_id,
                    "version": item.get("version", version),
                    "scenario": item.get("scenario", case.get("scenario")),
                    "experiment": item.get("experiment", case.get("experiment")),
                    "seed": item.get("seed", case.get("seed")),
                    "event_count": item.get("event_count", case.get("event_count")),
                    "phase": phase,
                    "attempt": data.get("attempt"),
                    "source_record": str(path.relative_to(ROOT)),
                    "record_status": _status(item.get("status", data.get("status"))),
                    "policy": (
                        _phase_policy(run_dir, str(phase), data)
                    ),
                    "environment": item.get("environment", {}),
                    "code_hashes": item.get("code_hashes", {}),
                    "input_checksums": item.get("input_checksums", case.get("input_checksums", {})),
                    "continuation_status": continuation_statuses.get((config_id, phase), ""),
                })
    return rows


def load_latency_samples(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Read a saved per-event latency artifact referenced by a result row."""
    relative = row.get("latency_raw_path")
    if not relative:
        return []
    artifact = (RESULTS / str(row["run_id"]) / str(relative).replace("\\", "/")).resolve()
    run_root = (RESULTS / str(row["run_id"])).resolve()
    if run_root not in artifact.parents or not artifact.is_file():
        return []
    samples = []
    with artifact.open(encoding="utf-8") as source:
        for line in source:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                samples.append(item)
    return samples


def _phase_records(run_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted((run_dir / "records").glob("*__attempt_*.json")):
        data = _read_json(path)
        if not data or data.get("record_type") == "configuration_attempt":
            continue
        config_id = data.get("config_id", "")
        case = data.get("case", {})
        phase = data.get("phase_job")
        grouped_rows: dict[str, list[dict[str, Any]]] = {}
        for row in data.get("rows", []):
            phase_name = phase or row.get("measurement_phase") or row.get("phase")
            if not phase_name:
                continue
            if phase_name.endswith("_summary"):
                phase_name = phase_name.removesuffix("_summary")
            grouped_rows.setdefault(phase_name, []).append(row)
        for phase_name, phase_rows in grouped_rows.items():
            states = [_status(row.get("status", data.get("status"))) for row in phase_rows]
            phase_status = "stopped" if any(state != "completed" for state in states) else "completed"
            sample = phase_rows[0]
            records.append({
                "config_id": config_id,
                "phase": phase_name,
                "status": phase_status,
                "policy": (
                    _phase_policy(run_dir, phase_name, data)
                ),
                "source_record": str(path.relative_to(ROOT)),
                "code_hashes": json.dumps(sample.get("code_hashes", {}), sort_keys=True),
                "input_checksums": json.dumps(
                    sample.get("input_checksums", case.get("input_checksums", {})), sort_keys=True
                ),
                "repeat_count": sum(
                    row.get("repeat") is not None
                    and _status(row.get("status", data.get("status"))) == "completed"
                    for row in phase_rows
                ),
                "counted_as_measurement": "true",
                "reuse_reference": "false",
                "decision": "executed raw phase record",
            })
    return records


def build_coverage_rows() -> list[dict[str, Any]]:
    """Reconcile saved phase attempts, resume references, and unattempted matrix cells."""
    output: list[dict[str, Any]] = []
    for run_dir in sorted(p for p in RESULTS.iterdir() if p.is_dir()):
        metadata = _read_json(run_dir / "metadata.json")
        if not metadata:
            continue
        cases = metadata.get("cases", [])
        attempts = _phase_records(run_dir)
        by_config: dict[str, list[dict[str, Any]]] = {}
        for item in attempts:
            by_config.setdefault(item["config_id"], []).append(item)
        summary_statuses: dict[tuple[str, str], Any] = {}
        for path in sorted((run_dir / "records").glob("*__attempt_*.json")):
            summary = _read_json(path)
            if not summary or summary.get("record_type") != "configuration_attempt":
                continue
            config_id = summary.get("config_id", "")
            phase_statuses = summary.get("phase_statuses", {})
            if isinstance(phase_statuses, dict):
                for name, value in phase_statuses.items():
                    summary_statuses[(config_id, name)] = (
                        value.get("status") if isinstance(value, dict) else value
                    )

        # A continuation plan supplies the expected phases and explicit reuse decisions.
        plans = sorted((run_dir / "continuation_plans").glob("*.json"))
        plan = _read_json(plans[-1]) if plans else None
        plan_configs = {
            entry.get("config_id"): entry
            for entry in (plan or {}).get("configs", [])
            if entry.get("config_id")
        }
        saved_cases: dict[str, dict[str, Any]] = {}
        for path in sorted((run_dir / "records").glob("*__attempt_*.json")):
            data = _read_json(path)
            if data and data.get("config_id") and isinstance(data.get("case"), dict):
                saved_cases[data["config_id"]] = data["case"]
        if plan_configs:
            config_items = [
                (config_id, entry.get("case") or saved_cases.get(config_id, {}))
                for config_id, entry in plan_configs.items()
            ]
        else:
            config_items_by_id = {
                f"{case.get('case_id', '')}__{version}": case
                for case in cases
                for version in ("baseline", "revised")
            }
            config_items_by_id.update(saved_cases)
            config_items = list(config_items_by_id.items())
        manifest = _read_json(run_dir / "CONTINUATION_STOP_20261126.json") or {}
        never_started = set(manifest.get("not_attempted_configs", []))
        interrupted_id = manifest.get("interrupted_mid_phase_config")

        for config_id, case in config_items:
                version = config_id.rsplit("__", 1)[-1]
                config_records = by_config.get(config_id, [])
                reuse_sources = {
                    item.get("phase"): item.get("source", "").replace("\\", "/")
                    for item in plan_configs.get(config_id, {}).get("phases", [])
                    if item.get("status") == "reusable" and item.get("source")
                }
                for record in config_records:
                    source_path = record["source_record"].replace("\\", "/")
                    decision = (
                        "original source measurement reused by continuation; counted once"
                        if reuse_sources.get(record["phase"]) == source_path
                        else record["decision"]
                    )
                    output.append({
                        "run_id": run_dir.name,
                        **case,
                        "config_id": config_id,
                        "version": version,
                        **record,
                        "decision": decision,
                        "configuration_status": (
                            "never_attempted" if config_id in never_started
                            else "interrupted" if config_id == interrupted_id
                            else "attempted"
                        ),
                    })
                expected: dict[str, dict[str, Any]] = {}
                plan_config = plan_configs.get(config_id, {})
                for phase in plan_config.get("phases", []):
                    expected[phase.get("phase", "")] = phase
                if not expected:
                    for record in config_records:
                        expected.setdefault(record["phase"], {})
                present = {r["phase"] for r in config_records}
                for phase_name, phase_plan in expected.items():
                    if phase_name in present:
                        continue
                    plan_status = phase_plan.get("status")
                    source = phase_plan.get("source")
                    recorded_status = summary_statuses.get((config_id, phase_name))
                    if plan_status == "reusable" and source:
                        status, reason = "completed", "compatible phase reused; source is referenced, not recounted"
                        counted, reuse = "false", "true"
                    elif config_id == interrupted_id and phase_name == "engine_replay":
                        status, reason, counted, reuse = "interrupted", "progress-only attempt at stop", "false", "false"
                    elif config_id in never_started:
                        status, reason, counted, reuse = "never_attempted", "listed in continuation stop manifest", "false", "false"
                    elif recorded_status in ("stopped_before_start", "stopped_timeout", "stopped_memory_limit", "error"):
                        status, reason, counted, reuse = "stopped", str(recorded_status), "false", "false"
                    elif plan_status in ("stopped_timeout", "stopped_memory_limit", "stopped_before_start", "error"):
                        status, reason, counted, reuse = "stopped", str(phase_plan.get("reason", plan_status)), "false", "false"
                    else:
                        status, reason, counted, reuse = "never_attempted", "no saved phase attempt", "false", "false"
                    output.append({
                        "run_id": run_dir.name,
                        **case,
                        "config_id": config_id,
                        "version": version,
                        "phase": phase_name,
                        "status": status,
                        "policy": _phase_policy(
                            run_dir, phase_name,
                            {
                                "record_type": "phase_attempt",
                                "phase_budget_seconds": phase_plan.get("budget_seconds"),
                            },
                        ) if phase_plan else "unknown",
                        "source_record": source or "",
                        "code_hashes": "",
                        "input_checksums": json.dumps(case.get("input_checksums", {}), sort_keys=True),
                        "repeat_count": 0,
                        "counted_as_measurement": counted,
                        "reuse_reference": reuse,
                        "configuration_status": (
                            "never_attempted" if config_id in never_started
                            else "interrupted" if config_id == interrupted_id
                            else "attempted"
                        ),
                        "decision": reason,
                    })
    return output


def write_coverage(path: Path | None = None) -> Path:
    destination = path or ROOT / "results" / "coverage.csv"
    rows = build_coverage_rows()
    fields = [
        "run_id", "case_id", "experiment", "scenario", "seed", "event_count",
        "config_id", "version", "phase", "status", "policy", "source_record",
        "code_hashes", "input_checksums", "repeat_count",
        "counted_as_measurement", "reuse_reference", "decision",
        "configuration_status",
    ]
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return destination


if __name__ == "__main__":
    print(write_coverage())

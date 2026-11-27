"""Separate warmed-primary controller built on the retained Stage 4D controller."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import run_benchmarks as core


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "07_results" / "stage4e" / "warmed_primary.jsonl"
WARMUP_ID = "02_data/generated/mixed_1000_seed42.jsonl.gz"
WARMUP_PATH = PROJECT_ROOT / WARMUP_ID
PROTOCOL = "warmed-primary-v1"


def _configure_core() -> None:
    warmup_sha256 = core._sha256(WARMUP_PATH.resolve(strict=True))
    os.environ["WARMED_PRIMARY_WARMUP_SHA256"] = warmup_sha256
    core.WORKER = Path(__file__).resolve().with_name("_warmed_primary_worker.py")
    core.FINAL_PROTOCOL_VERSION = PROTOCOL
    core.FINAL_PHASE = "warmed_primary"
    core.FINAL_MODE = "warmed_primary_timing"
    core.HARNESS_FILES = (
        "05_benchmarks/run_warmed_primary.py",
        "05_benchmarks/_warmed_primary_worker.py",
        "05_benchmarks/run_benchmarks.py",
    )
    original_templates = core._final_templates

    def warmed_templates(
        plan: list[dict[str, Any]], environment: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], int]:
        templates, unique_workloads = original_templates(plan, environment)
        for template in templates:
            template.update(
                warmup_workload_id=WARMUP_ID,
                warmup_event_count=1_000,
                warmup_sha256=warmup_sha256,
                warmup_policy=(
                    "same-process disposable same-class engine; process all warm-up events; "
                    "release; gc.collect; construct fresh empty measured engine"
                ),
            )
        return templates, unique_workloads

    core._final_templates = warmed_templates
    core._RESUME_FIELDS = (
        *core._RESUME_FIELDS,
        "warmup_workload_id",
        "warmup_event_count",
        "warmup_sha256",
        "warmup_policy",
    )


def _synthetic_self_test() -> None:
    plan = core._final_plan()
    templates, unique_workloads = core._final_templates(plan, core._environment())
    assert len(templates) == 450 and unique_workloads == 45
    assert len({_configuration(template) for template in templates}) == 90
    template = templates[0]
    completed = {
        **template,
        "status": "completed",
        "engine_seconds": 1.0,
        "snapshot_digest": "synthetic",
        "controller_wall_seconds": 1.5,
        "controller_session_id": "synthetic-session",
        "session_elapsed_seconds": 1.5,
    }
    core._validate_resume_records([completed], templates)
    for field in (
        "warmup_sha256",
        "warmup_policy",
        "implementation_fingerprint_sha256",
        "harness_fingerprint_sha256",
        "environment_fingerprint",
        "controller_protocol_version",
    ):
        changed = {**completed, field: "changed"}
        try:
            core._validate_resume_records([changed], templates)
        except ValueError as exc:
            assert "contradictory resume identity" in str(exc)
        else:
            raise AssertionError(f"resume accepted changed {field}")
    try:
        core._validate_resume_records([completed, completed], templates)
    except ValueError as exc:
        assert "duplicate logical repetition" in str(exc)
    else:
        raise AssertionError("duplicate warmed-primary repetition accepted")

    same_configuration = [
        item for item in templates if _configuration(item) == _configuration(template)
    ]
    same_configuration.sort(key=lambda item: item["repetition"])
    timeout_records = []
    for offset, item in enumerate(same_configuration):
        timeout_records.append(
            {
                **item,
                "status": "timed_out" if offset == 0 else "skipped_after_timeout",
                "controller_wall_seconds": 1.0 if offset == 0 else None,
                "controller_session_id": "timeout-session",
                "session_elapsed_seconds": float(offset + 1),
            }
        )
    core._validate_resume_records(timeout_records, templates)
    invalid_after_timeout = {
        **timeout_records[-1],
        "status": "completed",
        "engine_seconds": 1.0,
        "snapshot_digest": "x",
        "controller_wall_seconds": 1.0,
    }
    try:
        core._validate_resume_records([*timeout_records[:-1], invalid_after_timeout], templates)
    except ValueError as exc:
        assert "non-skipped record after timeout" in str(exc)
    else:
        raise AssertionError("completion after warmed-primary timeout accepted")

    with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
        fixture = Path(temporary) / "fixture.jsonl"
        fixture.write_text(json.dumps(completed), encoding="utf-8")
        try:
            core._read_jsonl_strict(fixture)
        except ValueError as exc:
            assert "truncated JSONL" in str(exc)
        else:
            raise AssertionError("truncated warmed-primary fixture accepted")
        fixture.write_text("{bad}\n", encoding="utf-8")
        try:
            core._read_jsonl_strict(fixture)
        except ValueError as exc:
            assert "malformed JSONL" in str(exc)
        else:
            raise AssertionError("malformed warmed-primary fixture accepted")
    print(json.dumps({
        "status": "passed",
        "planned_repetitions": 450,
        "configurations": 90,
        "unique_workloads": 45,
        "workers_launched": 0,
        "checks": [
            "valid_completed_resume", "warmup_hash", "warmup_policy",
            "implementation_fingerprint", "harness_fingerprint",
            "environment_fingerprint", "protocol_version", "duplicate",
            "timeout_then_skip", "completion_after_timeout", "truncated", "malformed",
        ],
    }, sort_keys=True))


def _configuration(record: dict[str, Any]) -> tuple[Any, ...]:
    return (
        record["engine"], record["scenario"], record["event_count"], record["seed"]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--global-budget-seconds", type=float, default=5_400.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    output = output.resolve()
    try:
        output.relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        parser.error("--output must resolve inside the approved project directory")
    if sum((args.dry_run, args.resume, args.self_test)) > 1:
        parser.error("--dry-run, --resume and --self-test are mutually exclusive")
    _configure_core()
    if args.self_test:
        _synthetic_self_test()
        return 0
    return core.run_final(
        output=output,
        budget=args.global_budget_seconds,
        resume=args.resume,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())

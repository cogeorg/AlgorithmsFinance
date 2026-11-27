"""Generate and verify the approved Stage 2B workload matrix."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
import platform
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from validate_inputs import validate_stream


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(__file__).resolve().parent
SUPPLIED_DIR = DATA_DIR / "supplied"
SUPPLIED_DATA_DIR = SUPPLIED_DIR / "data"
GENERATED_DIR = DATA_DIR / "generated"
STAGING_DIR = GENERATED_DIR / ".stage2b_staging"
GENERATOR_PATH = SUPPLIED_DIR / "generate_orders.py"
MANIFEST_PATH = DATA_DIR / "generated_manifest.json"

STAGE2B_V1_MANIFEST_SHA256 = "8e3a632738c6b61a57d6389e2154949c427e81397f97245d8dd0c7c4c97fd801"

EXPECTED_GENERATOR_SHA256 = "ef7f31545addf576e6071cc20a5930f3e2ed93bfef96d4968150fad763d7fe7d"
SCENARIOS = ("buildup", "crowded", "mixed", "sweep", "cancel_churn")
SEEDS = (42, 43, 44)
SOURCE_LEVELS = 1000
TARGET_BUCKETS = 4
BUY_REFERENCE = 6_000_000
SELL_REFERENCE = 6_000_100

MAX_OUTPUT_BYTES = 512 * 1024 * 1024
MAX_TOTAL_SECONDS = 30 * 60
PER_WORKLOAD_TIMEOUT_SECONDS = 120
APPROVED_NEW_EVENTS = 1_915_000


def timestamp() -> str:
    return datetime.now().astimezone().isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def metadata_path(workload_path: Path) -> Path:
    return workload_path.with_suffix(workload_path.suffix + ".metadata.json")


def generated_size() -> int:
    return sum(path.stat().st_size for path in GENERATED_DIR.rglob("*") if path.is_file())


def assert_within(path: Path, parent: Path) -> None:
    resolved = path.resolve()
    parent_resolved = parent.resolve()
    if resolved != parent_resolved and parent_resolved not in resolved.parents:
        raise RuntimeError(f"Path escapes approved directory: {resolved}")


def write_manifest(manifest: dict[str, Any]) -> None:
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def historical_execution_context() -> dict[str, Any]:
    return {
        "project_root": PROJECT_ROOT.as_posix(),
        "python": {
            "executable": sys.executable,
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "platform": platform.platform(),
        },
        "purpose": "Historical evidence from the machine that executed Stage 2B; not a portable command contract.",
    }


def portable_reproduction_contract() -> dict[str, Any]:
    return {
        "working_directory": "project_root",
        "path_rule": "All listed paths are relative to the project root.",
        "powershell_generate": ["python", "02_data/generate_workloads.py", "--execute"],
        "powershell_verify": ["python", "02_data/generate_workloads.py", "--verify-only"],
        "posix_generate": ["python3", "02_data/generate_workloads.py", "--execute"],
        "posix_verify": ["python3", "02_data/generate_workloads.py", "--verify-only"],
    }


def portable_direct_command(spec: dict[str, Any]) -> list[str]:
    return [
        "{python}",
        "02_data/supplied/generate_orders.py",
        "--scenario",
        str(spec["scenario"]),
        "--events",
        str(spec["events"]),
        "--levels",
        str(spec["levels"]),
        "--seed",
        str(spec["seed"]),
        "--out",
        f"02_data/generated/{spec['filename']}",
    ]


def semantic_inventory(manifest: dict[str, Any]) -> dict[str, Any]:
    direct_keys = (
        "kind", "scenario", "events", "seed", "levels", "filename", "sha256", "metadata_sha256"
    )
    paired_keys = (
        "kind", "scenario", "events", "seed", "source_levels", "effective_levels",
        "source_filename", "filename", "sha256", "metadata_sha256",
    )
    return {
        "direct_workloads": [
            {key: record[key] for key in direct_keys}
            for record in manifest["direct_workloads"]
        ],
        "paired_workloads": [
            {key: record[key] for key in paired_keys}
            for record in manifest["paired_workloads"]
        ],
        "supplied_core_coverage": manifest["supplied_core_coverage"],
    }


def object_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def core_specs() -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for scenario in SCENARIOS:
        for events, seeds in (
            (1_000, SEEDS),
            (10_000, (43, 44)),
            (100_000, SEEDS),
        ):
            for seed in seeds:
                specs.append(
                    {
                        "scenario": scenario,
                        "events": events,
                        "seed": seed,
                        "levels": SOURCE_LEVELS,
                        "filename": f"{scenario}_{events}_seed{seed}.jsonl.gz",
                    }
                )
    return specs


def paired_specs() -> list[dict[str, Any]]:
    return [
        {
            "scenario": "buildup",
            "events": 100_000,
            "seed": seed,
            "source_levels": SOURCE_LEVELS,
            "effective_levels": TARGET_BUCKETS,
            "source_filename": f"buildup_100000_seed{seed}.jsonl.gz",
            "filename": f"buildup_100000_seed{seed}_levels4_paired.jsonl.gz",
        }
        for seed in SEEDS
    ]


def preflight() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if sha256(GENERATOR_PATH) != EXPECTED_GENERATOR_SHA256:
        raise RuntimeError("Preserved instructor generator hash does not match the approved source")

    direct = core_specs()
    paired = paired_specs()
    filenames = [item["filename"] for item in direct + paired]
    if len(filenames) != 43 or len(set(filenames)) != 43:
        raise RuntimeError("Approved matrix must contain exactly 43 unique output names")
    if sum(item["events"] for item in direct + paired) != APPROVED_NEW_EVENTS:
        raise RuntimeError("Approved matrix event total changed")

    existing = list(GENERATED_DIR.iterdir())
    if existing:
        raise RuntimeError(
            "Generated directory must be empty before execution; found: "
            + ", ".join(path.name for path in existing)
        )
    if MANIFEST_PATH.exists():
        raise RuntimeError(f"Refusing to overwrite existing manifest: {MANIFEST_PATH}")

    if shutil.disk_usage(PROJECT_ROOT).free < MAX_OUTPUT_BYTES:
        raise RuntimeError("Less free disk space than the approved 512 MiB output limit")

    return direct, paired


def iter_events(path: Path) -> Iterator[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def coverage_metrics(path: Path) -> dict[str, Any]:
    type_counts: Counter[str] = Counter()
    side_counts: Counter[str] = Counter()
    price_counts: Counter[tuple[str, int]] = Counter()
    cancel_targets: Counter[str] = Counter()
    submission_seq: dict[str, int] = {}
    quantity_ranges: dict[str, list[int | None]] = {
        "LIMIT": [None, None],
        "MARKET_SELL": [None, None],
    }
    aggressive_limits: Counter[str] = Counter()
    max_type_runs: Counter[str] = Counter()
    current_type: str | None = None
    current_run = 0
    cancel_lags: list[int] = []

    for event in iter_events(path):
        event_type = event["type"]
        type_counts[event_type] += 1
        if event_type == current_type:
            current_run += 1
        else:
            if current_type is not None:
                max_type_runs[current_type] = max(max_type_runs[current_type], current_run)
            current_type = event_type
            current_run = 1

        if event_type == "LIMIT":
            side = event["side"]
            price = event["price_ticks"]
            side_counts[side] += 1
            price_counts[(side, price)] += 1
            submission_seq[event["order_id"]] = event["seq"]
            if side == "BUY" and price >= SELL_REFERENCE:
                aggressive_limits["BUY"] += 1
            if side == "SELL" and price <= BUY_REFERENCE:
                aggressive_limits["SELL"] += 1

        if event_type == "CANCEL":
            target = event["target_order_id"]
            cancel_targets[target] += 1
            if target in submission_seq:
                cancel_lags.append(event["seq"] - submission_seq[target])

        if event_type in quantity_ranges:
            quantity = event["qty_units"]
            current_min, current_max = quantity_ranges[event_type]
            quantity_ranges[event_type] = [
                quantity if current_min is None else min(current_min, quantity),
                quantity if current_max is None else max(current_max, quantity),
            ]

    if current_type is not None:
        max_type_runs[current_type] = max(max_type_runs[current_type], current_run)

    return {
        "event_type_counts": dict(sorted(type_counts.items())),
        "limit_side_counts": dict(sorted(side_counts.items())),
        "unique_limit_price_counts": {
            side: len({price for stored_side, price in price_counts if stored_side == side})
            for side in ("BUY", "SELL")
        },
        "max_submissions_at_one_price": {
            side: max(
                (count for (stored_side, _), count in price_counts.items() if stored_side == side),
                default=0,
            )
            for side in ("BUY", "SELL")
        },
        "aggressive_limit_counts": {
            side: aggressive_limits[side] for side in ("BUY", "SELL")
        },
        "repeated_cancel_target_count": sum(count > 1 for count in cancel_targets.values()),
        "maximum_cancel_attempts_for_one_target": max(cancel_targets.values(), default=0),
        "cancel_lag_range": (
            {"min": min(cancel_lags), "max": max(cancel_lags)} if cancel_lags else None
        ),
        "quantity_ranges": quantity_ranges,
        "maximum_consecutive_event_type_run": dict(sorted(max_type_runs.items())),
    }


def validate_metadata(
    workload: Path,
    metadata: Path,
    *,
    scenario: str,
    events: int,
    seed: int,
    levels: int,
) -> dict[str, Any]:
    value = json.loads(metadata.read_text(encoding="utf-8"))
    expected = {
        "scenario": scenario,
        "events": events,
        "seed": seed,
        "levels": levels,
        "compressed_bytes": workload.stat().st_size,
        "sha256": sha256(workload),
    }
    mismatches = {
        key: {"expected": expected_value, "actual": value.get(key)}
        for key, expected_value in expected.items()
        if value.get(key) != expected_value
    }
    if mismatches:
        raise RuntimeError(f"Metadata mismatch for {workload.name}: {mismatches}")
    return value


def validate_direct(path: Path, spec: dict[str, Any]) -> dict[str, Any]:
    structural = validate_stream(path)
    if structural["status"] != "valid":
        raise RuntimeError(f"Structural validation failed for {path.name}: {structural['errors']}")
    if structural["events"] != spec["events"]:
        raise RuntimeError(f"Wrong event count for {path.name}")
    if structural["first_seq"] != 1 or structural["last_seq"] != spec["events"]:
        raise RuntimeError(f"Wrong sequence range for {path.name}")

    metrics = coverage_metrics(path)
    counts = metrics["event_type_counts"]
    if spec["scenario"] in {"buildup", "crowded"} and counts != {"LIMIT": spec["events"]}:
        raise RuntimeError(f"Unexpected event types for {path.name}: {counts}")
    if spec["scenario"] == "cancel_churn" and counts != {
        "CANCEL": spec["events"] // 2,
        "LIMIT": spec["events"] // 2,
    }:
        raise RuntimeError(f"Unexpected cancel_churn composition for {path.name}: {counts}")
    if spec["scenario"] == "sweep" and counts != {
        "LIMIT": spec["events"] * 4 // 5,
        "MARKET_SELL": spec["events"] - spec["events"] * 4 // 5,
    }:
        raise RuntimeError(f"Unexpected sweep composition for {path.name}: {counts}")
    if spec["scenario"] == "mixed" and not {"LIMIT", "CANCEL", "MARKET_SELL"}.issubset(counts):
        raise RuntimeError(f"Mixed stream lacks an expected event type: {path.name}")
    if spec["scenario"] == "crowded" and metrics["unique_limit_price_counts"] != {
        "BUY": 4,
        "SELL": 4,
    }:
        raise RuntimeError(f"Crowded stream does not contain four prices per side: {path.name}")

    return {"structural": structural, "coverage_metrics": metrics}


def run_direct_generation(spec: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    staged = STAGING_DIR / spec["filename"]
    staged_metadata = metadata_path(staged)
    final = GENERATED_DIR / spec["filename"]
    final_metadata = metadata_path(final)
    for path in (staged, staged_metadata, final, final_metadata):
        if path.exists():
            raise RuntimeError(f"Refusing to overwrite: {path}")

    actual_command = [
        sys.executable,
        str(GENERATOR_PATH),
        "--scenario",
        spec["scenario"],
        "--events",
        str(spec["events"]),
        "--levels",
        str(spec["levels"]),
        "--seed",
        str(spec["seed"]),
        "--out",
        str(staged),
    ]
    historical_final_path_command = actual_command[:-1] + [str(final)]
    started = time.perf_counter()
    completed = subprocess.run(
        actual_command,
        check=False,
        capture_output=True,
        text=True,
        timeout=PER_WORKLOAD_TIMEOUT_SECONDS,
    )
    elapsed = time.perf_counter() - started
    if completed.returncode != 0:
        raise RuntimeError(
            f"Generator failed for {spec['filename']}: return={completed.returncode}; "
            f"stdout={completed.stdout!r}; stderr={completed.stderr!r}"
        )
    if not staged.is_file() or not staged_metadata.is_file():
        raise RuntimeError(f"Generator did not create both staged outputs for {spec['filename']}")

    validation = validate_direct(staged, spec)
    generated_metadata = validate_metadata(
        staged,
        staged_metadata,
        scenario=spec["scenario"],
        events=spec["events"],
        seed=spec["seed"],
        levels=spec["levels"],
    )

    staged.replace(final)
    staged_metadata.replace(final_metadata)
    return {
        "kind": "direct_generator_output",
        **spec,
        "status": "success",
        "actual_command": actual_command,
        "historical_final_path_command": historical_final_path_command,
        "portable_reproduction_command": portable_direct_command(spec),
        "elapsed_seconds": elapsed,
        "bytes": final.stat().st_size,
        "sha256": sha256(final),
        "metadata_path": final_metadata.relative_to(PROJECT_ROOT).as_posix(),
        "metadata_sha256": sha256(final_metadata),
        "generator_stdout": completed.stdout.strip(),
        "generator_stderr": completed.stderr.strip(),
        "generator_metadata": generated_metadata,
        **validation,
    }


def transformed_price(side: str, source_price: int) -> tuple[int, int, int]:
    if side == "BUY":
        depth = BUY_REFERENCE - source_price
    elif side == "SELL":
        depth = source_price - SELL_REFERENCE
    else:
        raise ValueError(f"Unexpected side: {side!r}")
    if not 0 <= depth < SOURCE_LEVELS:
        raise ValueError(f"Source depth {depth} is outside 0..{SOURCE_LEVELS - 1}")
    bucket = min(TARGET_BUCKETS - 1, depth * TARGET_BUCKETS // SOURCE_LEVELS)
    new_price = BUY_REFERENCE - bucket if side == "BUY" else SELL_REFERENCE + bucket
    return new_price, depth, bucket


def write_paired_stream(source: Path, destination: Path) -> dict[str, Any]:
    event_count = 0
    changed_price_count = 0
    with gzip.open(source, "rt", encoding="utf-8") as source_stream:
        with destination.open("wb") as raw:
            with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as compressed:
                for line in source_stream:
                    if not line.strip():
                        continue
                    event = json.loads(line)
                    if event.get("type") != "LIMIT":
                        raise RuntimeError("Paired concentration source must contain only LIMIT events")
                    old_price = event["price_ticks"]
                    new_price, _, _ = transformed_price(event["side"], old_price)
                    event["price_ticks"] = new_price
                    changed_price_count += new_price != old_price
                    event_count += 1
                    compressed.write(
                        (json.dumps(event, separators=(",", ":")) + "\n").encode("utf-8")
                    )
    return {"events": event_count, "changed_price_events": changed_price_count}


def verify_pair(source: Path, paired: Path) -> dict[str, Any]:
    events = 0
    non_price_mismatches = 0
    formula_mismatches = 0
    source_depth_range = [SOURCE_LEVELS, -1]
    source_to_transformed: dict[str, dict[int, int]] = {"BUY": {}, "SELL": {}}
    source_quantities: Counter[str] = Counter()
    paired_quantities: Counter[str] = Counter()
    paired_prices: dict[str, set[int]] = {"BUY": set(), "SELL": set()}

    source_iterator = iter_events(source)
    paired_iterator = iter_events(paired)
    for source_event, paired_event in itertools.zip_longest(source_iterator, paired_iterator):
        if source_event is None or paired_event is None:
            raise RuntimeError("Source and paired stream lengths differ")
        events += 1
        if source_event.keys() != paired_event.keys():
            non_price_mismatches += 1
            continue

        source_without_price = dict(source_event)
        paired_without_price = dict(paired_event)
        source_price = source_without_price.pop("price_ticks")
        paired_price = paired_without_price.pop("price_ticks")
        if source_without_price != paired_without_price:
            non_price_mismatches += 1

        expected_price, depth, _ = transformed_price(source_event["side"], source_price)
        if paired_price != expected_price:
            formula_mismatches += 1
        source_depth_range[0] = min(source_depth_range[0], depth)
        source_depth_range[1] = max(source_depth_range[1], depth)
        source_to_transformed[source_event["side"]][source_price] = paired_price
        source_quantities[source_event["side"]] += source_event["qty_units"]
        paired_quantities[paired_event["side"]] += paired_event["qty_units"]
        paired_prices[paired_event["side"]].add(paired_price)

    monotonic = True
    for side, mapping in source_to_transformed.items():
        ordered_source_prices = sorted(mapping, reverse=(side == "BUY"))
        ordered_transformed = [mapping[price] for price in ordered_source_prices]
        if side == "BUY":
            monotonic &= all(
                ordered_transformed[index] >= ordered_transformed[index + 1]
                for index in range(len(ordered_transformed) - 1)
            )
        else:
            monotonic &= all(
                ordered_transformed[index] <= ordered_transformed[index + 1]
                for index in range(len(ordered_transformed) - 1)
            )

    result = {
        "events": events,
        "non_price_mismatches": non_price_mismatches,
        "formula_mismatches": formula_mismatches,
        "source_depth_range": {"min": source_depth_range[0], "max": source_depth_range[1]},
        "unique_paired_prices": {
            side: sorted(prices, reverse=(side == "BUY")) for side, prices in paired_prices.items()
        },
        "source_quantities": dict(source_quantities),
        "paired_quantities": dict(paired_quantities),
        "quantity_totals_equal": source_quantities == paired_quantities,
        "monotonic": monotonic,
        "uncrossed": max(paired_prices["BUY"]) < min(paired_prices["SELL"]),
    }
    expected_prices = {"BUY": 4, "SELL": 4}
    actual_price_counts = {side: len(prices) for side, prices in paired_prices.items()}
    if (
        non_price_mismatches
        or formula_mismatches
        or not result["quantity_totals_equal"]
        or not monotonic
        or not result["uncrossed"]
        or actual_price_counts != expected_prices
    ):
        raise RuntimeError(f"Paired verification failed: {result}")
    return result


def run_paired_generation(spec: dict[str, Any]) -> dict[str, Any]:
    source = GENERATED_DIR / spec["source_filename"]
    staged = STAGING_DIR / spec["filename"]
    staged_metadata = metadata_path(staged)
    final = GENERATED_DIR / spec["filename"]
    final_metadata = metadata_path(final)
    if not source.is_file():
        raise RuntimeError(f"Missing paired source: {source}")
    for path in (staged, staged_metadata, final, final_metadata):
        if path.exists():
            raise RuntimeError(f"Refusing to overwrite: {path}")

    started = time.perf_counter()
    transform_summary = write_paired_stream(source, staged)
    structural = validate_stream(staged)
    if structural["status"] != "valid" or structural["events"] != spec["events"]:
        raise RuntimeError(f"Paired stream structural validation failed: {structural}")
    pair_verification = verify_pair(source, staged)
    metrics = coverage_metrics(staged)

    metadata = {
        "synthetic": True,
        "calibrated_to_exchange_data": False,
        "derived": True,
        "scenario": spec["scenario"],
        "events": spec["events"],
        "seed": spec["seed"],
        "source_levels": spec["source_levels"],
        "effective_levels": spec["effective_levels"],
        "source_path": source.relative_to(PROJECT_ROOT).as_posix(),
        "source_sha256": sha256(source),
        "transformation": {
            "depth": "BUY: 6000000-price_ticks; SELL: price_ticks-6000100",
            "bucket": "min(3, (depth * 4) // 1000)",
            "price": "BUY: 6000000-bucket; SELL: 6000100+bucket",
            "changed_field": "price_ticks",
        },
        "python": platform.python_version(),
        "transform_script": Path(__file__).relative_to(PROJECT_ROOT).as_posix(),
        "transform_script_sha256": sha256(Path(__file__)),
        "price_tick_usd": "0.01",
        "quantity_unit_btc": "0.00000001",
        "compressed_bytes": staged.stat().st_size,
        "sha256": sha256(staged),
    }
    staged_metadata.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    staged.replace(final)
    staged_metadata.replace(final_metadata)
    return {
        "kind": "paired_price_only_transformation",
        **spec,
        "status": "success",
        "elapsed_seconds": time.perf_counter() - started,
        "bytes": final.stat().st_size,
        "sha256": sha256(final),
        "metadata_path": final_metadata.relative_to(PROJECT_ROOT).as_posix(),
        "metadata_sha256": sha256(final_metadata),
        "transform_summary": transform_summary,
        "pair_verification": pair_verification,
        "structural": structural,
        "coverage_metrics": metrics,
    }


def deterministic_spot_check(source: Path, final_paired: Path) -> dict[str, Any]:
    temporary = STAGING_DIR / "determinism_check_buildup_100000_seed42_levels4_paired.jsonl.gz"
    assert_within(temporary, STAGING_DIR)
    if temporary.exists():
        raise RuntimeError(f"Determinism staging file already exists: {temporary}")
    write_paired_stream(source, temporary)
    first_hash = sha256(final_paired)
    second_hash = sha256(temporary)
    matched = first_hash == second_hash
    if not matched:
        raise RuntimeError("Paired deterministic spot check failed")
    temporary.unlink()
    return {
        "source": source.relative_to(PROJECT_ROOT).as_posix(),
        "final": final_paired.relative_to(PROJECT_ROOT).as_posix(),
        "temporary_path": temporary.relative_to(PROJECT_ROOT).as_posix(),
        "sha256": first_hash,
        "matched": True,
        "temporary_removed": not temporary.exists(),
    }


def supplied_coverage() -> list[dict[str, Any]]:
    return [
        {
            "scenario": scenario,
            "events": 10_000,
            "seed": 42,
            "path": f"02_data/supplied/data/{scenario}_10000.jsonl.gz",
            "sha256": sha256(SUPPLIED_DATA_DIR / f"{scenario}_10000.jsonl.gz"),
        }
        for scenario in SCENARIOS
    ]


def final_verification(
    direct_specs: list[dict[str, Any]],
    paired_workloads: list[dict[str, Any]],
) -> dict[str, Any]:
    workloads = sorted(GENERATED_DIR.glob("*.jsonl.gz"))
    metadata_files = sorted(GENERATED_DIR.glob("*.jsonl.gz.metadata.json"))
    if len(workloads) != 43 or len(metadata_files) != 43:
        raise RuntimeError(
            f"Expected 43 workloads and metadata files; found {len(workloads)} and {len(metadata_files)}"
        )
    if generated_size() > MAX_OUTPUT_BYTES:
        raise RuntimeError("Generated directory exceeds approved 512 MiB limit")

    core_keys = {
        (item["scenario"], item["events"], item["seed"])
        for item in direct_specs
    }
    core_keys.update((scenario, 10_000, 42) for scenario in SCENARIOS)
    expected_core_keys = {
        (scenario, events, seed)
        for scenario in SCENARIOS
        for events in (1_000, 10_000, 100_000)
        for seed in SEEDS
    }
    if core_keys != expected_core_keys:
        raise RuntimeError("Core matrix does not cover the required 45 combinations")

    for paired_record in paired_workloads:
        source = GENERATED_DIR / paired_record["source_filename"]
        paired = GENERATED_DIR / paired_record["filename"]
        verify_pair(source, paired)

    return {
        "generated_workload_count": len(workloads),
        "generated_metadata_count": len(metadata_files),
        "core_combination_count_including_supplied": len(core_keys),
        "paired_workload_count": len(paired_workloads),
        "generated_directory_bytes": generated_size(),
        "all_generated_sha256": {
            path.name: sha256(path) for path in workloads
        },
    }


def execute() -> None:
    direct_specs, transform_specs = preflight()
    STAGING_DIR.mkdir(parents=False, exist_ok=False)
    started_wall = time.perf_counter()
    manifest: dict[str, Any] = {
        "schema_version": 2,
        "status": "running",
        "started_at": timestamp(),
        "historical_execution_context": historical_execution_context(),
        "portable_reproduction": portable_reproduction_contract(),
        "command_semantics": {
            "actual_command": "Exact command executed historically; may contain machine-specific absolute paths.",
            "historical_final_path_command": "Historical equivalent targeting the finalized path; retained as evidence, not portability guidance.",
            "portable_reproduction_command": "Project-root-relative command template; replace {python} with python or python3.",
        },
        "generator": {
            "path": GENERATOR_PATH.relative_to(PROJECT_ROOT).as_posix(),
            "sha256": sha256(GENERATOR_PATH),
            "unchanged_from_instructor": True,
        },
        "resource_limits": {
            "new_workloads": 43,
            "new_events": APPROVED_NEW_EVENTS,
            "per_workload_timeout_seconds": PER_WORKLOAD_TIMEOUT_SECONDS,
            "total_wall_seconds": MAX_TOTAL_SECONDS,
            "generated_directory_max_bytes": MAX_OUTPUT_BYTES,
            "parallel_generators": 1,
            "million_event_workloads": 0,
        },
        "supplied_core_coverage": supplied_coverage(),
        "direct_workloads": [],
        "paired_workloads": [],
        "failures": [],
    }
    write_manifest(manifest)

    try:
        for index, spec in enumerate(direct_specs, start=1):
            if time.perf_counter() - started_wall > MAX_TOTAL_SECONDS:
                raise TimeoutError("Approved total Stage 2B generation time exceeded")
            print(
                f"CORE {index:02d}/{len(direct_specs)} "
                f"{spec['scenario']} events={spec['events']} seed={spec['seed']}",
                flush=True,
            )
            record = run_direct_generation(spec, manifest)
            manifest["direct_workloads"].append(record)
            if generated_size() > MAX_OUTPUT_BYTES:
                raise RuntimeError("Generated directory exceeds approved 512 MiB limit")
            write_manifest(manifest)

        for index, spec in enumerate(transform_specs, start=1):
            print(
                f"PAIRED {index:02d}/{len(transform_specs)} seed={spec['seed']}",
                flush=True,
            )
            record = run_paired_generation(spec)
            manifest["paired_workloads"].append(record)
            if generated_size() > MAX_OUTPUT_BYTES:
                raise RuntimeError("Generated directory exceeds approved 512 MiB limit")
            write_manifest(manifest)

        manifest["determinism_spot_check"] = deterministic_spot_check(
            GENERATED_DIR / "buildup_100000_seed42.jsonl.gz",
            GENERATED_DIR / "buildup_100000_seed42_levels4_paired.jsonl.gz",
        )
        if any(STAGING_DIR.iterdir()):
            raise RuntimeError("Unexpected files remain in the exact Stage 2B staging directory")
        STAGING_DIR.rmdir()

        manifest["final_verification"] = final_verification(
            direct_specs,
            manifest["paired_workloads"],
        )
        elapsed = time.perf_counter() - started_wall
        if elapsed > MAX_TOTAL_SECONDS:
            raise TimeoutError("Approved total Stage 2B time exceeded")
        manifest["elapsed_seconds"] = elapsed
        manifest["completed_at"] = timestamp()
        manifest["status"] = "complete"
        write_manifest(manifest)
        print(json.dumps(manifest["final_verification"], indent=2), flush=True)
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["failed_at"] = timestamp()
        manifest["failures"].append({"type": type(exc).__name__, "message": str(exc)})
        write_manifest(manifest)
        raise


def verify_only() -> None:
    direct = core_specs()
    if not MANIFEST_PATH.is_file():
        raise RuntimeError("Generated manifest is missing")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("status") != "complete":
        raise RuntimeError("Generated manifest is not complete")
    for spec in direct:
        workload = GENERATED_DIR / spec["filename"]
        metadata = metadata_path(workload)
        validate_direct(workload, spec)
        validate_metadata(
            workload,
            metadata,
            scenario=spec["scenario"],
            events=spec["events"],
            seed=spec["seed"],
            levels=spec["levels"],
        )
    result = final_verification(direct, manifest["paired_workloads"])
    print(json.dumps(result, indent=2))


def migrate_manifest_v2() -> None:
    if not MANIFEST_PATH.is_file():
        raise RuntimeError("Generated manifest is missing")
    previous_sha256 = sha256(MANIFEST_PATH)
    if previous_sha256 != STAGE2B_V1_MANIFEST_SHA256:
        raise RuntimeError(
            "Refusing migration because the manifest does not match the approved Stage 2B v1 hash: "
            f"{previous_sha256}"
        )

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or manifest.get("status") != "complete":
        raise RuntimeError("Manifest is not the completed Stage 2B schema-v1 record")

    semantic_before = object_sha256(semantic_inventory(manifest))
    actual_commands_before = object_sha256(
        [record["actual_command"] for record in manifest["direct_workloads"]]
    )
    old_project_root = manifest.pop("project_root")
    old_python = manifest.pop("python")
    manifest["schema_version"] = 2
    manifest["historical_execution_context"] = {
        "project_root": old_project_root,
        "python": old_python,
        "purpose": "Historical evidence from the machine that executed Stage 2B; not a portable command contract.",
    }
    manifest["portable_reproduction"] = portable_reproduction_contract()
    manifest["command_semantics"] = {
        "actual_command": "Exact command executed historically; may contain machine-specific absolute paths.",
        "historical_final_path_command": "Historical equivalent targeting the finalized path; retained as evidence, not portability guidance.",
        "portable_reproduction_command": "Project-root-relative command template; replace {python} with python or python3.",
    }
    for record in manifest["direct_workloads"]:
        record["historical_final_path_command"] = record.pop("reproduction_command")
        record["portable_reproduction_command"] = portable_direct_command(record)

    semantic_after = object_sha256(semantic_inventory(manifest))
    actual_commands_after = object_sha256(
        [record["actual_command"] for record in manifest["direct_workloads"]]
    )
    if semantic_after != semantic_before:
        raise RuntimeError("Semantic workload inventory changed during manifest migration")
    if actual_commands_after != actual_commands_before:
        raise RuntimeError("Historical actual commands changed during manifest migration")

    manifest["manifest_migration"] = {
        "migrated_at": timestamp(),
        "previous_schema_version": 1,
        "previous_manifest_sha256": previous_sha256,
        "semantic_inventory_sha256_before_and_after": semantic_before,
        "actual_commands_sha256_before_and_after": actual_commands_before,
        "result": "Only command labeling, portable reproduction fields, and execution-context labeling changed.",
    }
    write_manifest(manifest)
    print(f"Previous manifest SHA-256: {previous_sha256}")
    print(f"New manifest SHA-256: {sha256(MANIFEST_PATH)}")
    print(f"Semantic inventory SHA-256: {semantic_after}")
    print(f"Historical actual commands SHA-256: {actual_commands_after}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--execute", action="store_true", help="Run the approved Stage 2B generation plan")
    mode.add_argument("--verify-only", action="store_true", help="Revalidate finalized Stage 2B outputs")
    mode.add_argument(
        "--migrate-manifest-v2",
        action="store_true",
        help="Migrate the exact approved Stage 2B schema-v1 manifest to portable schema v2",
    )
    args = parser.parse_args()
    if args.execute:
        execute()
    elif args.verify_only:
        verify_only()
    else:
        migrate_manifest_v2()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Generate and verify the approved 10,000-event four-level concentration pairs."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
import os
import platform
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIR = PROJECT_ROOT / "02_data" / "generated"
SUPPLIED_DIR = PROJECT_ROOT / "02_data" / "supplied" / "data"
MANIFEST_PATH = PROJECT_ROOT / "02_data" / "concentration_10000_manifest.json"
STAGING_DIR = PROJECT_ROOT / "02_data" / ".stage4e_concentration_staging"
BUY_REFERENCE = 6_000_000
SELL_REFERENCE = 6_000_100
SOURCE_LEVELS = 1_000
TARGET_BUCKETS = 4
MAX_SECONDS = 30.0
MAX_FINAL_BYTES = 5 * 1024 * 1024
SEEDS = (42, 43, 44)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_path(seed: int) -> Path:
    if seed == 42:
        return SUPPLIED_DIR / "buildup_10000.jsonl.gz"
    return GENERATED_DIR / f"buildup_10000_seed{seed}.jsonl.gz"


def output_path(seed: int) -> Path:
    return GENERATED_DIR / f"buildup_10000_seed{seed}_levels4_paired.jsonl.gz"


def metadata_path(workload: Path) -> Path:
    return workload.with_suffix(workload.suffix + ".metadata.json")


def iter_events(path: Path) -> Iterator[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                raise ValueError(f"blank JSONL line {line_number}: {path}")
            event = json.loads(line)
            if type(event) is not dict:
                raise TypeError(f"line {line_number} is not an object: {path}")
            yield event


def transformed_price(side: str, source_price: int) -> tuple[int, int, int]:
    """Exact Stage 2B monotonic four-bucket price transformation."""
    if side == "BUY":
        depth = BUY_REFERENCE - source_price
    elif side == "SELL":
        depth = source_price - SELL_REFERENCE
    else:
        raise ValueError(f"unexpected side: {side!r}")
    if not 0 <= depth < SOURCE_LEVELS:
        raise ValueError(f"source depth {depth} is outside 0..{SOURCE_LEVELS - 1}")
    bucket = min(TARGET_BUCKETS - 1, depth * TARGET_BUCKETS // SOURCE_LEVELS)
    new_price = BUY_REFERENCE - bucket if side == "BUY" else SELL_REFERENCE + bucket
    return new_price, depth, bucket


def write_pair(source: Path, destination: Path) -> dict[str, int]:
    events = 0
    changed = 0
    with destination.open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as compressed:
            for event in iter_events(source):
                if event.get("type") != "LIMIT":
                    raise ValueError("concentration source contains a non-LIMIT event")
                old_price = event["price_ticks"]
                new_price, _, _ = transformed_price(event["side"], old_price)
                transformed = dict(event)
                transformed["price_ticks"] = new_price
                compressed.write(
                    (json.dumps(transformed, separators=(",", ":")) + "\n").encode("utf-8")
                )
                events += 1
                changed += new_price != old_price
    return {"events": events, "changed_price_events": changed}


def verify_pair(source: Path, paired: Path) -> dict[str, Any]:
    events = 0
    non_price_mismatches = 0
    formula_mismatches = 0
    previous_seq: int | None = None
    source_quantities: Counter[str] = Counter()
    paired_quantities: Counter[str] = Counter()
    paired_prices: dict[str, set[int]] = {"BUY": set(), "SELL": set()}
    mapping: dict[str, dict[int, int]] = {"BUY": {}, "SELL": {}}

    for source_event, paired_event in itertools.zip_longest(
        iter_events(source), iter_events(paired)
    ):
        if source_event is None or paired_event is None:
            raise ValueError("source and paired stream lengths differ")
        events += 1
        if previous_seq is not None and source_event["seq"] <= previous_seq:
            raise ValueError("source sequence is not strictly increasing")
        previous_seq = source_event["seq"]
        if source_event.keys() != paired_event.keys():
            non_price_mismatches += 1
            continue
        source_without_price = dict(source_event)
        paired_without_price = dict(paired_event)
        source_price = source_without_price.pop("price_ticks")
        paired_price = paired_without_price.pop("price_ticks")
        if source_without_price != paired_without_price:
            non_price_mismatches += 1
        expected, _, _ = transformed_price(source_event["side"], source_price)
        if paired_price != expected:
            formula_mismatches += 1
        side = source_event["side"]
        mapping[side][source_price] = paired_price
        source_quantities[side] += source_event["qty_units"]
        paired_quantities[side] += paired_event["qty_units"]
        paired_prices[side].add(paired_price)

    monotonic = True
    for side, side_mapping in mapping.items():
        ordered_source = sorted(side_mapping, reverse=(side == "BUY"))
        ordered_paired = [side_mapping[price] for price in ordered_source]
        if side == "BUY":
            monotonic &= all(a >= b for a, b in itertools.pairwise(ordered_paired))
        else:
            monotonic &= all(a <= b for a, b in itertools.pairwise(ordered_paired))

    result = {
        "events": events,
        "non_price_mismatches": non_price_mismatches,
        "formula_mismatches": formula_mismatches,
        "quantity_totals_equal": source_quantities == paired_quantities,
        "source_quantities": dict(source_quantities),
        "paired_quantities": dict(paired_quantities),
        "unique_paired_prices": {
            side: sorted(prices, reverse=(side == "BUY"))
            for side, prices in paired_prices.items()
        },
        "monotonic": monotonic,
        "uncrossed": max(paired_prices["BUY"]) < min(paired_prices["SELL"]),
    }
    if (
        events != 10_000
        or non_price_mismatches
        or formula_mismatches
        or not result["quantity_totals_equal"]
        or not monotonic
        or not result["uncrossed"]
        or {side: len(prices) for side, prices in paired_prices.items()}
        != {"BUY": 4, "SELL": 4}
    ):
        raise ValueError(f"pair verification failed: {result}")
    return result


def metadata(seed: int, source: Path, output: Path) -> dict[str, Any]:
    return {
        "synthetic": True,
        "calibrated_to_exchange_data": False,
        "derived": True,
        "scenario": "buildup",
        "events": 10_000,
        "seed": seed,
        "source_levels": SOURCE_LEVELS,
        "effective_levels": TARGET_BUCKETS,
        "source_path": source.relative_to(PROJECT_ROOT).as_posix(),
        "source_sha256": sha256(source),
        "output_path": output.relative_to(PROJECT_ROOT).as_posix(),
        "output_sha256": sha256(output),
        "compressed_bytes": output.stat().st_size,
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
    }


def cleanup_staging() -> None:
    resolved = STAGING_DIR.resolve()
    expected_parent = (PROJECT_ROOT / "02_data").resolve()
    if resolved.parent != expected_parent or resolved.name != ".stage4e_concentration_staging":
        raise RuntimeError(f"refusing unsafe staging cleanup: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def execute() -> None:
    started = time.perf_counter()
    targets = [MANIFEST_PATH]
    for seed in SEEDS:
        targets.extend((output_path(seed), metadata_path(output_path(seed))))
    existing = [path for path in targets if path.exists()]
    if existing:
        raise FileExistsError(f"refusing to overwrite: {[str(path) for path in existing]}")
    if STAGING_DIR.exists():
        raise FileExistsError(f"staging directory already exists: {STAGING_DIR}")
    for seed in SEEDS:
        if not source_path(seed).is_file():
            raise FileNotFoundError(f"source is absent: {source_path(seed)}")

    STAGING_DIR.mkdir()
    records: list[dict[str, Any]] = []
    try:
        for seed in SEEDS:
            source = source_path(seed)
            first = STAGING_DIR / f"seed{seed}_first.jsonl.gz"
            second = STAGING_DIR / f"seed{seed}_second.jsonl.gz"
            transform_summary = write_pair(source, first)
            pair_verification = verify_pair(source, first)
            write_pair(source, second)
            first_hash = sha256(first)
            second_hash = sha256(second)
            if first_hash != second_hash:
                raise ValueError(f"deterministic second pass differs for seed {seed}")
            final = output_path(seed)
            first.replace(final)
            second.unlink()
            meta = metadata(seed, source, final)
            meta_path = metadata_path(final)
            meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            records.append(
                {
                    "seed": seed,
                    "source_path": source.relative_to(PROJECT_ROOT).as_posix(),
                    "source_sha256": sha256(source),
                    "output_path": final.relative_to(PROJECT_ROOT).as_posix(),
                    "output_bytes": final.stat().st_size,
                    "output_sha256": first_hash,
                    "metadata_path": meta_path.relative_to(PROJECT_ROOT).as_posix(),
                    "metadata_sha256": sha256(meta_path),
                    "deterministic_second_pass_sha256": second_hash,
                    "transform_summary": transform_summary,
                    "pair_verification": pair_verification,
                }
            )
            if time.perf_counter() - started > MAX_SECONDS:
                raise TimeoutError("generation exceeded the approved 30-second ceiling")

        finalized = [output_path(seed) for seed in SEEDS] + [
            metadata_path(output_path(seed)) for seed in SEEDS
        ]
        total_bytes = sum(path.stat().st_size for path in finalized)
        if total_bytes > MAX_FINAL_BYTES:
            raise ValueError("finalized outputs exceed the approved 5 MiB ceiling")
        manifest = {
            "schema_version": 1,
            "status": "complete",
            "purpose": "Stage 4E 10,000-event four-level price-only concentration pairs",
            "working_directory": "project_root",
            "generator_path": Path(__file__).relative_to(PROJECT_ROOT).as_posix(),
            "generator_sha256": sha256(Path(__file__)),
            "python": platform.python_version(),
            "resource_limits": {
                "maximum_seconds": MAX_SECONDS,
                "maximum_finalized_bytes": MAX_FINAL_BYTES,
            },
            "portable_commands": {
                "execute": "{python} 02_data/generate_concentration_pairs.py --execute",
                "verify": "{python} 02_data/generate_concentration_pairs.py --verify-only",
            },
            "formula": {
                "depth": "BUY: 6000000-price_ticks; SELL: price_ticks-6000100",
                "bucket": "min(3, (depth * 4) // 1000)",
                "price": "BUY: 6000000-bucket; SELL: 6000100+bucket",
                "changed_field": "price_ticks",
            },
            "total_finalized_bytes": total_bytes,
            "elapsed_seconds": time.perf_counter() - started,
            "pairs": records,
        }
        temporary_manifest = STAGING_DIR / "manifest.json"
        temporary_manifest.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        temporary_manifest.replace(MANIFEST_PATH)
    finally:
        cleanup_staging()


def verify_only() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("generator_sha256") != sha256(Path(__file__)):
        raise ValueError("generator hash differs from retained manifest")
    for record in manifest["pairs"]:
        source = PROJECT_ROOT / record["source_path"]
        output = PROJECT_ROOT / record["output_path"]
        meta = PROJECT_ROOT / record["metadata_path"]
        if sha256(source) != record["source_sha256"]:
            raise ValueError(f"source hash mismatch: {source}")
        if sha256(output) != record["output_sha256"]:
            raise ValueError(f"output hash mismatch: {output}")
        if sha256(meta) != record["metadata_sha256"]:
            raise ValueError(f"metadata hash mismatch: {meta}")
        verify_pair(source, output)
    print(json.dumps({"status": "verified", "pairs": len(manifest["pairs"])}, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--execute", action="store_true")
    modes.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.execute:
        execute()
    else:
        verify_only()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

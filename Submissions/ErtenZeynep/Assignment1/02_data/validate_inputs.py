"""Validate supplied or generated assignment inputs without matching orders."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUPPLIED_DIR = Path(__file__).resolve().parent / "supplied"

REQUIRED_FIELDS = {
    "LIMIT": {"seq", "event_id", "type", "order_id", "side", "price_ticks", "qty_units"},
    "MARKET_SELL": {"seq", "event_id", "type", "order_id", "qty_units"},
    "CANCEL": {"seq", "event_id", "type", "target_order_id"},
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_cli_path(value: str | None, default: Path) -> Path:
    path = default if value is None else Path(value).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def validate_event(event: Any, line_number: int, previous_seq: int | None) -> list[str]:
    errors: list[str] = []
    if not isinstance(event, dict):
        return [f"line {line_number}: event is not a JSON object"]

    event_type = event.get("type")
    if event_type not in REQUIRED_FIELDS:
        return [f"line {line_number}: invalid event type {event_type!r}"]

    missing = REQUIRED_FIELDS[event_type] - event.keys()
    if missing:
        errors.append(f"line {line_number}: missing fields {sorted(missing)}")

    seq = event.get("seq")
    if type(seq) is not int or seq <= 0:
        errors.append(f"line {line_number}: seq is not a positive exact integer")
    elif previous_seq is not None and seq <= previous_seq:
        errors.append(f"line {line_number}: seq {seq} is not greater than {previous_seq}")

    if not isinstance(event.get("event_id"), str) or not event.get("event_id"):
        errors.append(f"line {line_number}: event_id is not a nonempty string")

    if event_type in {"LIMIT", "MARKET_SELL"}:
        if not isinstance(event.get("order_id"), str) or not event.get("order_id"):
            errors.append(f"line {line_number}: order_id is not a nonempty string")
        quantity = event.get("qty_units")
        if type(quantity) is not int or quantity <= 0:
            errors.append(f"line {line_number}: qty_units is not a positive exact integer")

    if event_type == "LIMIT":
        if event.get("side") not in {"BUY", "SELL"}:
            errors.append(f"line {line_number}: invalid LIMIT side {event.get('side')!r}")
        price = event.get("price_ticks")
        if type(price) is not int or price <= 0:
            errors.append(f"line {line_number}: price_ticks is not a positive exact integer")

    if event_type == "CANCEL":
        target = event.get("target_order_id")
        if not isinstance(target, str) or not target:
            errors.append(f"line {line_number}: target_order_id is not a nonempty string")

    return errors


def validate_stream(path: Path) -> dict[str, Any]:
    opener = gzip.open if path.suffix == ".gz" else open
    event_counts: Counter[str] = Counter()
    event_ids: set[str] = set()
    submission_ids: set[str] = set()
    duplicate_event_ids: list[str] = []
    duplicate_submission_ids: list[str] = []
    limit_side_counts: Counter[str] = Counter()
    limit_prices: dict[str, set[int]] = {"BUY": set(), "SELL": set()}
    errors: list[str] = []
    first_seq: int | None = None
    previous_seq: int | None = None
    line_count = 0

    try:
        with opener(path, "rt", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    errors.append(f"line {line_number}: blank line")
                    continue
                line_count += 1
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as exc:
                    errors.append(f"line {line_number}: JSON error: {exc.msg}")
                    continue

                errors.extend(validate_event(event, line_number, previous_seq))
                if not isinstance(event, dict):
                    continue

                seq = event.get("seq")
                if type(seq) is int:
                    if first_seq is None:
                        first_seq = seq
                    previous_seq = seq

                event_type = event.get("type")
                event_counts[str(event_type)] += 1

                event_id = event.get("event_id")
                if isinstance(event_id, str):
                    if event_id in event_ids:
                        duplicate_event_ids.append(event_id)
                    event_ids.add(event_id)

                if event_type in {"LIMIT", "MARKET_SELL"}:
                    order_id = event.get("order_id")
                    if isinstance(order_id, str):
                        if order_id in submission_ids:
                            duplicate_submission_ids.append(order_id)
                        submission_ids.add(order_id)

                if event_type == "LIMIT":
                    side = event.get("side")
                    price = event.get("price_ticks")
                    if side in limit_prices and type(price) is int:
                        limit_side_counts[side] += 1
                        limit_prices[side].add(price)
    except (OSError, UnicodeError) as exc:
        errors.append(f"stream read failure: {exc}")

    if duplicate_event_ids:
        errors.append(f"duplicate event IDs: {sorted(set(duplicate_event_ids))[:10]}")
    if duplicate_submission_ids:
        errors.append(f"duplicate submission IDs: {sorted(set(duplicate_submission_ids))[:10]}")

    return {
        "path": path.as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "events": line_count,
        "first_seq": first_seq,
        "last_seq": previous_seq,
        "event_type_counts": dict(sorted(event_counts.items())),
        "limit_side_counts": dict(sorted(limit_side_counts.items())),
        "unique_limit_price_counts": {
            side: len(prices) for side, prices in sorted(limit_prices.items())
        },
        "limit_price_ranges": {
            side: ({"min": min(prices), "max": max(prices)} if prices else None)
            for side, prices in sorted(limit_prices.items())
        },
        "unique_event_ids": len(event_ids),
        "unique_submission_ids": len(submission_ids),
        "errors": errors,
        "status": "valid" if not errors else "invalid",
    }


def verify_manifest(supplied_dir: Path) -> dict[str, Any]:
    manifest_path = supplied_dir / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    comparisons: list[dict[str, Any]] = []
    listed_paths = set(manifest["files"])

    for relative_path, expected in manifest["files"].items():
        path = supplied_dir / Path(relative_path)
        if not path.is_file():
            comparisons.append({
                "path": relative_path,
                "status": "missing",
                "expected_bytes": expected["bytes"],
                "expected_sha256": expected["sha256"],
            })
            continue
        actual_hash = sha256(path)
        actual_bytes = path.stat().st_size
        comparisons.append({
            "path": relative_path,
            "status": "matched" if actual_bytes == expected["bytes"] and actual_hash == expected["sha256"] else "mismatched",
            "expected_bytes": expected["bytes"],
            "actual_bytes": actual_bytes,
            "expected_sha256": expected["sha256"],
            "actual_sha256": actual_hash,
        })

    actual_paths = {
        path.relative_to(supplied_dir).as_posix()
        for path in supplied_dir.rglob("*")
        if path.is_file()
    }
    unlisted = sorted(actual_paths - listed_paths)
    return {
        "manifest_path": manifest_path.as_posix(),
        "assignment": manifest.get("assignment"),
        "synthetic_data_only": manifest.get("synthetic_data_only"),
        "comparisons": comparisons,
        "unlisted_actual_files": unlisted,
    }


def verify_metadata(data_dir: Path, stream_results: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for metadata_path in sorted(data_dir.glob("*.jsonl.gz.metadata.json")):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        stream_path = metadata_path.with_suffix("").with_suffix("")
        relative_stream = stream_path.relative_to(data_dir.parent).as_posix()
        stream = stream_results.get(relative_stream)
        errors: list[str] = []
        if stream is None:
            errors.append("referenced stream was not validated")
        else:
            if metadata.get("events") != stream["events"]:
                errors.append("metadata event count does not match stream")
            if metadata.get("compressed_bytes") != stream["bytes"]:
                errors.append("metadata byte count does not match stream")
            if metadata.get("sha256") != stream["sha256"]:
                errors.append("metadata SHA-256 does not match stream")
        results.append({
            "path": metadata_path.relative_to(data_dir.parent).as_posix(),
            "scenario": metadata.get("scenario"),
            "events": metadata.get("events"),
            "seed": metadata.get("seed"),
            "levels": metadata.get("levels"),
            "python": metadata.get("python"),
            "stream_path": relative_stream,
            "errors": errors,
            "status": "valid" if not errors else "invalid",
        })
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--supplied-dir", help="Package root; relative paths resolve against the current working directory")
    parser.add_argument("--output", help="JSON report path; relative paths resolve against the current working directory")
    args = parser.parse_args()

    supplied_dir = resolve_cli_path(args.supplied_dir, DEFAULT_SUPPLIED_DIR)
    output_path = resolve_cli_path(args.output, Path(__file__).resolve().parent / "supplied_verification.json")
    data_dir = supplied_dir / "data"

    stream_paths = sorted(data_dir.glob("*.jsonl.gz")) + [data_dir / "worked_example.jsonl"]
    stream_results = {
        path.relative_to(supplied_dir).as_posix(): validate_stream(path)
        for path in stream_paths
        if path.is_file()
    }

    worked_expected_path = data_dir / "worked_expected.json"
    worked_expected = json.loads(worked_expected_path.read_text(encoding="utf-8"))
    report = {
        "project_root": PROJECT_ROOT.as_posix(),
        "supplied_dir": supplied_dir.as_posix(),
        "manifest_verification": verify_manifest(supplied_dir),
        "streams": stream_results,
        "metadata_verification": verify_metadata(data_dir, stream_results),
        "worked_expected": {
            "path": worked_expected_path.relative_to(supplied_dir).as_posix(),
            "bytes": worked_expected_path.stat().st_size,
            "sha256": sha256(worked_expected_path),
            "top_level_keys": sorted(worked_expected),
            "fill_count": len(worked_expected.get("market_sell_result", {}).get("fills", [])),
            "remaining_order_count": len(worked_expected.get("remaining_orders", [])),
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "supplied_dir": supplied_dir.as_posix(),
        "output": output_path.as_posix(),
        "streams": len(stream_results),
        "invalid_streams": sum(result["status"] != "valid" for result in stream_results.values()),
        "invalid_metadata": sum(result["status"] != "valid" for result in report["metadata_verification"]),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Record and check checksums of the generated benchmark streams (data/generated/).

For every data/generated/*.jsonl.gz it records
  - sha256 of the .gz file   (depends on the zlib version: NOT a proof of identical content)
  - sha256 of the decompressed JSON Lines (independent of zlib: this proves identical events)
together with the generator settings from the file's .metadata.json.

    .venv/bin/python tools/hash_generated.py --write   # writes results/generated_data_checksums.json
    .venv/bin/python tools/hash_generated.py --check   # recompute and compare (decompressed hash)
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import platform
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GENERATED = ROOT / "data" / "generated"
RECORD = ROOT / "results" / "generated_data_checksums.json"


def file_hashes(gz: Path) -> tuple[str, str, int]:
    """(sha256 of the .gz, sha256 of the decompressed text, number of events)."""
    gz_hash, plain_hash, events = hashlib.sha256(), hashlib.sha256(), 0
    with gz.open("rb") as raw:
        for block in iter(lambda: raw.read(1 << 20), b""):
            gz_hash.update(block)
    with gzip.open(gz, "rb") as stream:
        for line in stream:
            plain_hash.update(line)
            events += 1
    return gz_hash.hexdigest(), plain_hash.hexdigest(), events


def collect() -> dict:
    files = {}
    for gz in sorted(GENERATED.glob("*.jsonl.gz")):
        meta = json.loads(gz.with_name(gz.name + ".metadata.json").read_text())
        gz_sha, plain_sha, events = file_hashes(gz)
        if events != meta["events"]:
            raise SystemExit(f"{gz.name}: {events} events, metadata says {meta['events']}")
        files[gz.name] = {
            "scenario": meta["scenario"], "events": events, "seed": meta["seed"],
            "levels": meta["levels"], "gz_bytes": gz.stat().st_size,
            "gz_sha256": gz_sha, "decompressed_sha256": plain_sha,
            "command": (f"python generate_orders.py --scenario {meta['scenario']} "
                        f"--events {events} --levels {meta['levels']} --seed {meta['seed']} "
                        f"--out data/generated/{gz.name}"),
        }
    return {
        "note": ("decompressed_sha256 proves identical events; gz_sha256 also depends on the "
                 "zlib version used to compress"),
        "environment": {"python": platform.python_version(), "zlib": zlib.ZLIB_VERSION,
                        "platform": platform.platform()},
        "files": files,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    current = collect()
    if args.write:
        RECORD.parent.mkdir(exist_ok=True)
        RECORD.write_text(json.dumps(current, indent=2) + "\n")
        print(f"wrote {RECORD.relative_to(ROOT)}: {len(current['files'])} files")
        return 0
    recorded = json.loads(RECORD.read_text())["files"]
    problems = [f"missing in record: {n}" for n in current["files"] if n not in recorded]
    problems += [f"file missing: {n}" for n in recorded if n not in current["files"]]
    for name, info in current["files"].items():
        old = recorded.get(name)
        if old and old["decompressed_sha256"] != info["decompressed_sha256"]:
            problems.append(f"decompressed content differs: {name}")
        elif old and old["gz_sha256"] != info["gz_sha256"]:
            print(f"note: {name}: .gz bytes differ (other zlib?), decompressed content equal")
    for p in problems:
        print("PROBLEM:", p)
    print(f"checked {len(current['files'])} files, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

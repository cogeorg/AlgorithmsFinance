"""Check the supplied files against MANIFEST.json and the .metadata.json files.

For every data/*.jsonl.gz it reports
  - sha256 of the .gz file (what the course metadata records; depends on the zlib version)
  - sha256 of the decompressed JSON Lines (independent of the zlib version)
  - event count and event-type counts
and writes results/data_checksums.json. Usage (from Assignment1/):
    .venv/bin/python tools/verify_data.py
"""
from __future__ import annotations

import collections
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Course files kept under docs/ so this folder's own README.md can describe the submission.
RELOCATED = {"README.md": "docs/ASSIGNMENT_README.md",
             "AlgorithmsFinance_Exercise1.pdf": "docs/AlgorithmsFinance_Exercise1.pdf"}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    manifest = json.loads((ROOT / "MANIFEST.json").read_text())["files"]
    report, problems = {}, []

    for rel, info in manifest.items():
        path = ROOT / RELOCATED.get(rel, rel)
        if rel == ".DS_Store":            # listed in the course manifest, not shipped
            continue
        if not path.exists():
            problems.append(f"missing: {rel}")
            continue
        if sha256(path.read_bytes()) != info["sha256"]:
            problems.append(f"manifest sha256 mismatch: {rel}")

    for gz in sorted((ROOT / "data").glob("*.jsonl.gz")):
        raw = gz.read_bytes()
        plain = gzip.decompress(raw)
        meta = json.loads(gz.with_name(gz.name + ".metadata.json").read_text())
        types = collections.Counter(json.loads(line)["type"]
                                    for line in plain.decode().splitlines() if line)
        entry = {
            "gz_sha256": sha256(raw),
            "gz_sha256_matches_metadata": sha256(raw) == meta["sha256"],
            "decompressed_sha256": sha256(plain),
            "events": sum(types.values()),
            "types": dict(types),
            "scenario": meta["scenario"], "seed": meta["seed"], "levels": meta["levels"],
        }
        if not entry["gz_sha256_matches_metadata"]:
            problems.append(f"metadata sha256 mismatch: {gz.name}")
        if entry["events"] != meta["events"]:
            problems.append(f"event count mismatch: {gz.name}")
        report[gz.name] = entry
        print(f"{gz.name:32s} events={entry['events']:>6} "
              f"gz_ok={entry['gz_sha256_matches_metadata']} "
              f"decompressed={entry['decompressed_sha256'][:16]}...")

    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "data_checksums.json").write_text(json.dumps(report, indent=2) + "\n")
    print("OK: all supplied files match" if not problems else "\n".join(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())

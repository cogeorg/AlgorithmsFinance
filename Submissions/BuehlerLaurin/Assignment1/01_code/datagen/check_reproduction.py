"""Check that the SUPPLIED generator reproduces the SUPPLIED 10,000-event samples byte for byte.

Usage (from the exercise root):
    python run.py datagen.check_reproduction --generator <package>/generate_orders.py

For each of the five scenarios it runs the course generator (seed 42, 10,000 events,
1,000 levels, as recorded in the supplied *.metadata.json files) into
06_data/generated/repro/ and compares the SHA-256 of the new file with the sha256 in
06_data/supplied/<scenario>_10000.jsonl.gz.metadata.json. Generation happens here,
outside any timing. Exit code 1 if any file differs or is missing.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

SCENARIOS = ("buildup", "crowded", "mixed", "sweep", "cancel_churn")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--generator", type=Path, required=True, help="path to the supplied generate_orders.py")
    ap.add_argument("--supplied", type=Path, default=Path("06_data/supplied"))
    ap.add_argument("--out", type=Path, default=Path("06_data/generated/repro"))
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    print(f"generator: {a.generator} sha256={sha256(a.generator)}")
    print(f"python:    {sys.version.split()[0]}")
    failed = False
    for sc in SCENARIOS:
        meta = json.loads((a.supplied / f"{sc}_10000.jsonl.gz.metadata.json").read_text(encoding="utf-8"))
        out = a.out / f"{sc}_{meta['events']}_seed{meta['seed']}.jsonl.gz"
        cmd = [sys.executable, "-I", str(a.generator), "--scenario", sc, "--events", str(meta["events"]),
               "--levels", str(meta["levels"]), "--seed", str(meta["seed"]), "--out", str(out)]
        subprocess.run(cmd, check=True, capture_output=True)
        got, want = sha256(out), meta["sha256"]
        ok = got == want
        failed |= not ok
        print(f"{'OK      ' if ok else 'MISMATCH'} {sc:<13} seed={meta['seed']} events={meta['events']} "
              f"levels={meta['levels']} sha256={got}")
    print(f"RESULT: {'FAIL' if failed else 'PASS'} ({len(SCENARIOS)} scenarios regenerated)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

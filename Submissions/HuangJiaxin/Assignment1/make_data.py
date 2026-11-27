"""Generate the benchmark datasets OUTSIDE any timing, and record their checksums.

Run from this folder:
    python make_data.py              # grid used by the benchmarks (about 1 minute)
    python make_data.py --million    # additionally the one-million-event streams

The generator `generate_orders.py` is the course-provided script, copied unchanged
(its SHA-256 matches the course MANIFEST.json). Generated files go to data/generated/,
which is not committed; data/generated_manifest.json records the exact command, settings
and SHA-256 of every file, so anyone can regenerate and verify them.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GEN = HERE / "generate_orders.py"
OUT = HERE / "data" / "generated"
SUPPLIED = HERE / "data" / "supplied"

SCENARIOS = ["buildup", "crowded", "mixed", "sweep", "cancel_churn"]
SIZES = [1_000, 10_000, 100_000]
SEEDS = [42, 43, 44]
LEVELS = 1000
CONCENTRATION_LEVELS = 4          # compared with LEVELS = 1000 at the same event count
MILLION = [("buildup", 42), ("mixed", 42), ("cancel_churn", 42)]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def plan(million):
    """(scenario, events, seed, levels, filename) for every dataset."""
    jobs = []
    for s in SCENARIOS:
        for m in SIZES:
            for seed in SEEDS:
                jobs.append((s, m, seed, LEVELS, f"{s}_{m}_s{seed}_L{LEVELS}.jsonl.gz"))
    for m in [10_000, 100_000]:                       # queue concentration experiment
        for seed in SEEDS:
            jobs.append(("buildup", m, seed, CONCENTRATION_LEVELS,
                         f"buildup_{m}_s{seed}_L{CONCENTRATION_LEVELS}.jsonl.gz"))
    if million:
        for s, seed in MILLION:
            jobs.append((s, 1_000_000, seed, LEVELS, f"{s}_1000000_s{seed}_L{LEVELS}.jsonl.gz"))
    return jobs


def check_supplied():
    """The supplied 10,000-event samples must match the course checksums."""
    manifest = json.loads((SUPPLIED / "MANIFEST.json").read_text())["files"]
    ok = True
    for name, info in manifest.items():
        local = SUPPLIED / Path(name).name
        if name.startswith("data/") and local.exists():
            same = sha256(local) == info["sha256"]
            ok &= same
            print(f"supplied {local.name}: {'OK' if same else 'CHECKSUM MISMATCH'}")
    same = sha256(GEN) == manifest["generate_orders.py"]["sha256"]
    print(f"generate_orders.py unchanged: {'OK' if same else 'CHANGED'}")
    return ok and same


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--million", action="store_true", help="also generate 1,000,000-event streams")
    args = ap.parse_args()
    if not check_supplied():
        sys.exit("supplied files or generator differ from the course manifest")
    OUT.mkdir(parents=True, exist_ok=True)
    manifest_path = HERE / "data" / "generated_manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    for scenario, events, seed, levels, name in plan(args.million):
        path = OUT / name
        cmd = [sys.executable, str(GEN), "--scenario", scenario, "--events", str(events),
               "--levels", str(levels), "--seed", str(seed), "--out", str(path)]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
        manifest[name] = {
            "command": f"python generate_orders.py --scenario {scenario} --events {events} "
                       f"--levels {levels} --seed {seed} --out data/generated/{name}",
            "scenario": scenario, "events": events, "seed": seed, "levels": levels,
            "bytes": path.stat().st_size, "sha256": sha256(path),
        }
        print(f"{name}: {path.stat().st_size:,} bytes")
    manifest_path.write_text(json.dumps(dict(sorted(manifest.items())), indent=2) + "\n")
    print(f"wrote {manifest_path.relative_to(HERE)} ({len(manifest)} files)")


if __name__ == "__main__":
    main()

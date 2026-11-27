#!/usr/bin/env python3
"""Generate all benchmark inputs OUTSIDE timing, with the unchanged course generator.

Writes data/generated/*.jsonl.gz (git-ignored) and results/generated_inputs.json with
the exact commands and SHA-256 checksums so the files can be regenerated and verified.
"""
import hashlib
import json
import subprocess
import sys

from _util import GEN, MILLION, RESULTS, ROOT, SCENARIOS, SEEDS, SIZES, input_path, save_json

QUEUE_CONCENTRATION = [("buildup", 10000, 42, 4), ("buildup", 10000, 42, 1000),
                       ("buildup", 100000, 42, 4)]


def configs():
    for scenario in SCENARIOS:
        for events in SIZES:
            for seed in SEEDS:
                yield scenario, events, seed, 1000
    for scenario, events, seed in MILLION:
        yield scenario, events, seed, 1000
    yield from QUEUE_CONCENTRATION


def main():
    GEN.mkdir(parents=True, exist_ok=True)
    manifest = []
    for scenario, events, seed, levels in dict.fromkeys(configs()):
        out = input_path(scenario, events, seed, levels)
        cmd = [sys.executable, "generate_orders.py", "--scenario", scenario, "--events", str(events),
               "--levels", str(levels), "--seed", str(seed), "--out", str(out.relative_to(ROOT))]
        if not out.exists():
            subprocess.run(cmd, check=True, cwd=ROOT, capture_output=True)
        sha = hashlib.sha256(out.read_bytes()).hexdigest()
        manifest.append({"file": str(out.relative_to(ROOT)), "scenario": scenario, "events": events,
                         "seed": seed, "levels": levels, "sha256": sha,
                         "command": "python generate_orders.py " + " ".join(cmd[2:])})
        print(f"{out.name:45s} {sha[:16]}")
    # Reproducibility check: the generated 10k/seed-42 files must equal the supplied samples.
    same = {}
    for scenario in SCENARIOS:
        supplied = ROOT / "data" / f"{scenario}_10000.jsonl.gz"
        same[scenario] = (hashlib.sha256(supplied.read_bytes()).hexdigest()
                          == hashlib.sha256(input_path(scenario, 10000, 42).read_bytes()).hexdigest())
    save_json(RESULTS / "generated_inputs.json",
              {"files": manifest, "identical_to_supplied_10000_seed42_samples": same})
    print(json.dumps(same))


if __name__ == "__main__":
    main()

"""Generate the scaling datasets with the professor's generator (outside timing).

Usage (from Assignment1/):
    python 04_benchmarks/generate_data.py [--sizes 1000 10000 30000 100000] [--seed 42]

Writes 05_results/data/<scenario>_<M>.jsonl.gz plus the generator's
.metadata.json (SHA-256 checksum). The .jsonl.gz files are gitignored;
the metadata files are kept so a reviewer can check a regenerated file.
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "00_instructions" / "generate_orders.py"
OUT_DIR = ROOT / "05_results" / "data"
SCENARIOS = ["buildup", "crowded", "mixed", "sweep", "cancel_churn"]


def data_path(scenario, events):
    return OUT_DIR / f"{scenario}_{events}.jsonl.gz"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=int, nargs="+",
                        default=[1000, 10000, 30000, 100000])
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    for m in args.sizes:
        for scenario in SCENARIOS:
            out = data_path(scenario, m)
            subprocess.run([sys.executable, str(GENERATOR), "--scenario", scenario,
                            "--events", str(m), "--seed", str(args.seed),
                            "--out", str(out)], check=True, stdout=subprocess.DEVNULL)
            print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

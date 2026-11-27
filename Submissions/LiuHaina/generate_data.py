"""Generate saved, deterministic inputs; no algorithm calls or timing here."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import random


SIZES = (1_000, 10_000, 100_000)
QUERY_COUNTS = (1, 100)
SCENARIOS = ("all_present", "all_absent", "mixed")


def array_hash(array):
    encoded = json.dumps(array, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_dataset(seed=42, include_empty_queries=False):
    arrays, cases, skipped = {}, [], []
    for n in SIZES:
        array_seed = seed + n
        rng = random.Random(array_seed)
        # Sampling with replacement deliberately creates duplicates.
        domain_size = n // 2
        array = [rng.randrange(domain_size) for _ in range(n)]
        array_id = f"n{n}"
        arrays[array_id] = {
            "n": n, "seed": array_seed, "values": array,
            "sha256": array_hash(array),
            "distinct_count": len(set(array)),
            "id_domain": [0, domain_size - 1],
        }
        for q in QUERY_COUNTS:
            for scenario_index, scenario in enumerate(SCENARIOS):
                case_id = f"n{n}_q{q}_{scenario}"
                if scenario == "mixed" and q < 2:
                    skipped.append({
                        "case_id": case_id,
                        "reason": "One query cannot contain both a hit and a miss.",
                    })
                    continue
                query_seed = seed + n * 1_000 + q * 10 + scenario_index
                query_rng = random.Random(query_seed)
                hits = q if scenario == "all_present" else (q // 2 if scenario == "mixed" else 0)
                # Hits sample array positions, so frequent IDs are more likely.
                queries = [query_rng.choice(array) for _ in range(hits)]
                # Negative IDs cannot occur in the nonnegative input arrays.
                queries += [-query_rng.randint(1, n) for _ in range(q - hits)]
                query_rng.shuffle(queries)
                cases.append({
                    "case_id": case_id, "array_id": array_id,
                    "n": n, "q": q, "scenario": scenario,
                    "query_seed": query_seed, "queries": queries,
                    "hit_count": hits, "hit_rate": hits / q,
                    "expected": [value >= 0 for value in queries],
                    "supplementary": False,
                })
        if include_empty_queries:
            cases.append({
                "case_id": f"n{n}_q0_empty", "array_id": array_id,
                "n": n, "q": 0, "scenario": "empty_queries",
                "query_seed": None, "queries": [], "expected": [],
                "hit_count": 0, "hit_rate": None, "supplementary": True,
            })
    return {
        "schema_version": 1,
        "generator": {
            "base_seed": seed,
            "include_empty_queries": include_empty_queries,
            "python_version": platform.python_version(),
            "random_engine": "random.Random (Mersenne Twister)",
            "array_seed_rule": "base_seed + n",
            "query_seed_rule": "base_seed + n*1000 + q*10 + scenario_index",
            "scenario_order": list(SCENARIOS),
            "duplicate_policy": "Array IDs sampled uniformly with replacement from range(n//2); queries may repeat.",
            "hit_sampling": "Sample existing array positions uniformly with replacement.",
            "miss_sampling": "Sample negative integers uniformly with replacement from [-n, -1].",
            "mixed_policy": "Exactly half hits for q=100; q=1 skipped as infeasible.",
            "empty_hit_rate": "null: no queries, so a hit rate is undefined",
        },
        "arrays": arrays, "cases": cases, "skipped_cases": skipped,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--include-empty-queries", action="store_true")
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).resolve().parent / "data" / "inputs.json")
    args = parser.parse_args()
    dataset = build_dataset(args.seed, args.include_empty_queries)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dataset, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(dataset['arrays'])} arrays and {len(dataset['cases'])} cases to {args.output}")
    print(f"Skipped {len(dataset['skipped_cases'])} infeasible q=1 mixed cases (reasons saved).")


if __name__ == "__main__":
    main()

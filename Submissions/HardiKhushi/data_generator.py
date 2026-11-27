"""Reproducible synthetic inputs; no searching, timing, or file writes."""

import argparse
from dataclasses import asdict, dataclass
import json
import random


GENERATOR_VERSION = "1"
SCENARIOS = ("all-present", "all-absent", "mixed")
DUPLICATE_POLICIES = ("unique", "repeated")


@dataclass
class Workload:
    ids: list[int]
    queries: list[int]
    expected: list[bool]
    settings: dict


def generate_workload(n, q, *, seed=42, scenario="mixed", duplicate_policy="unique"):
    """Return IDs, queries, known answers, and settings for one shared workload.

    Present IDs occupy [0, distinct_ids); absent queries occupy [n, 2*n),
    or use 0 when n is zero. Mixed batches alternate hits/misses before
    shuffling, giving one extra hit when q is odd. Repeated queries are allowed.
    The repeated policy cycles through ceil(n/2) distinct IDs before shuffling.
    """
    if n < 0 or q < 0:
        raise ValueError("n and q must be nonnegative")
    if scenario not in SCENARIOS:
        raise ValueError(f"scenario must be one of {SCENARIOS}")
    if duplicate_policy not in DUPLICATE_POLICIES:
        raise ValueError(f"duplicate_policy must be one of {DUPLICATE_POLICIES}")
    if n == 0 and q > 0 and scenario != "all-absent":
        raise ValueError("present queries require at least one input ID")

    # A local RNG avoids changing randomness elsewhere in the project.
    # Adding n preserves the initial benchmark's seed convention.
    effective_seed = seed + n
    rng = random.Random(effective_seed)
    distinct_ids = n if duplicate_policy == "unique" else (n + 1) // 2
    ids = [i % distinct_ids for i in range(n)]
    rng.shuffle(ids)
    queries = []
    for i in range(q):
        present = scenario == "all-present" or (scenario == "mixed" and i % 2 == 0)
        query = rng.randrange(distinct_ids) if present else n + rng.randrange(max(n, 1))
        queries.append(query)
    rng.shuffle(queries)
    # The disjoint value ranges give known answers without calling a search method.
    expected = [0 <= query < distinct_ids for query in queries]
    settings = {
        "generator_version": GENERATOR_VERSION, "n": n, "queries": q,
        "seed": seed, "effective_seed": effective_seed, "scenario": scenario,
        "hit_count": sum(expected), "hit_rate": sum(expected) / q if q else 0.0,
        "duplicate_policy": duplicate_policy, "distinct_ids": distinct_ids,
        "query_duplicates": "allowed",
    }
    return Workload(ids, queries, expected, settings)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=10)
    parser.add_argument("--queries", type=int, default=6)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--scenario", choices=SCENARIOS, default="mixed")
    parser.add_argument("--duplicate-policy", choices=DUPLICATE_POLICIES, default="unique")
    args = parser.parse_args()
    try:
        workload = generate_workload(args.n, args.queries, seed=args.seed,
                                     scenario=args.scenario,
                                     duplicate_policy=args.duplicate_policy)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(asdict(workload), indent=2))


if __name__ == "__main__":
    main()

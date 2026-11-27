import argparse
import json
import math
import random
from numbers import Real
from pathlib import Path


GENERATOR_VERSION = "1.0.0"


def generate_case(
    n: int, q: int, hit_rate: Real, seed: int
) -> dict[str, object]:
    """Generate reproducible IDs and queries with independently computed answers."""
    for name, value in (("n", n), ("q", q)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer.")

    if (
        isinstance(hit_rate, bool)
        or not isinstance(hit_rate, Real)
        or not 0 <= hit_rate <= 1
        or not math.isfinite(float(hit_rate))
    ):
        raise ValueError("hit_rate must be a finite number between 0 and 1.")

    requested_rate = float(hit_rate)
    requested_hits = int(q * hit_rate + 0.5)
    if requested_hits > 0 and n == 0:
        raise ValueError(
            f"{requested_hits} hits requested, but n=0 provides no IDs."
        )

    rng = random.Random(seed)
    id_max = 10 * n
    ids = [rng.randint(0, id_max) for _ in range(n)]

    queries = [rng.choice(ids) for _ in range(requested_hits)]
    queries.extend(-rng.randint(1, q) for _ in range(q - requested_hits))
    rng.shuffle(queries)

    id_set = set(ids)
    expected_answers = [query in id_set for query in queries]
    actual_hit_count = sum(expected_answers)

    return {
        "ids": ids,
        "queries": queries,
        "expected_answers": expected_answers,
        "metadata": {
            "seed": seed,
            "n": n,
            "q": q,
            "requested_hit_rate": requested_rate,
            "actual_hit_count": actual_hit_count,
            "actual_hit_rate": actual_hit_count / q if q else None,
            "duplicate_policy": (
                "IDs are sampled with replacement from the inclusive range "
                "[0, 10*n]; duplicates are allowed."
            ),
            "id_range": {"min": 0, "max": id_max} if n else None,
            "absent_query_policy": (
                "Absent queries are negative integers sampled with "
                "replacement from [-q, -1]; they cannot match non-negative "
                "IDs. No absent queries are generated when q=0."
            ),
            "generator_version": GENERATOR_VERSION,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a synthetic finance lab case."
    )
    parser.add_argument("--n", type=int, required=True, help="number of IDs")
    parser.add_argument("--q", type=int, required=True, help="number of queries")
    parser.add_argument(
        "--hit-rate",
        type=float,
        required=True,
        help="requested fraction of queries present in the IDs (0 to 1)",
    )
    parser.add_argument("--seed", type=int, required=True, help="random seed")
    parser.add_argument(
        "--output", type=Path, help="optional path to save the generated JSON"
    )
    args = parser.parse_args(argv)

    try:
        case = generate_case(args.n, args.q, args.hit_rate, args.seed)
    except ValueError as error:
        parser.error(str(error))

    output = json.dumps(case, indent=2)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

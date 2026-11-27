"""Create and verify the 18 fixed input files for later comparisons."""

import json
from pathlib import Path

from synthetic_data import generate_data


SIZES = (1_000, 10_000, 100_000)
QUERY_COUNTS = (1, 100)
SCENARIOS = {"present": 1.0, "absent": 0.0, "mixed": 0.5}
SEED = 42
DATA_DIR = Path(__file__).resolve().parent / "data"


def validate(data, n, q, scenario, requested_rate):
    ids, queries = data["ids"], data["queries"]
    expected_hits = int(q * requested_rate + 0.5)
    present = set(ids)
    actual_hits = sum(query in present for query in queries)

    if data["n"] != n or len(ids) != n or data["q"] != q or len(queries) != q:
        raise ValueError("ID or query count does not match the filename")
    if not all(type(value) is int for value in ids + queries):
        raise ValueError("IDs and queries must contain only integers")
    if ids == sorted(ids):
        raise ValueError("Saved IDs must remain unsorted")
    if (data["scenario"] != scenario or
            data["requested_hit_rate"] != requested_rate or
            data["actual_hit_rate"] != expected_hits / q or
            data["seed"] != SEED or data["allow_duplicates"] is not True):
        raise ValueError("Dataset metadata does not match the requested parameters")
    if actual_hits != expected_hits:
        raise ValueError("Query hits do not match the requested scenario")
    if (ids, queries) != generate_data(n, q, requested_rate, True, SEED):
        raise ValueError("Dataset is not reproducible from the recorded parameters")


def main():
    DATA_DIR.mkdir(exist_ok=True)
    count = 0
    for n in SIZES:
        for q in QUERY_COUNTS:
            for scenario, rate in SCENARIOS.items():
                ids, queries = generate_data(n, q, rate, True, SEED)
                present = set(ids)
                actual_hits = sum(query in present for query in queries)
                data = {
                    "n": n,
                    "q": q,
                    "scenario": scenario,
                    "requested_hit_rate": rate,
                    "actual_hit_rate": actual_hits / q,
                    "seed": SEED,
                    "allow_duplicates": True,
                    "ids": ids,
                    "queries": queries,
                }
                validate(data, n, q, scenario, rate)
                path = DATA_DIR / f"n{n}_q{q}_{scenario}.json"
                if not path.exists():
                    path.write_text(json.dumps(data, separators=(",", ":")) + "\n",
                                    encoding="utf-8")
                saved = json.loads(path.read_text(encoding="utf-8"))
                validate(saved, n, q, scenario, rate)
                if saved != data:
                    raise ValueError(f"Saved input changed: {path}")
                count += 1
    print(f"Validated {count} fixed datasets in {DATA_DIR}")


if __name__ == "__main__":
    main()

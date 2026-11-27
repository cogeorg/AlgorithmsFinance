"""Check saved experiment inputs and both implementations; not a benchmark."""

import argparse
import importlib
import json
from pathlib import Path

from generate_data import QUERY_COUNTS, SCENARIOS, SIZES, array_hash, build_dataset


METHODS = ("linear_search", "binary_search", "hash_set_search")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path,
                        default=Path(__file__).resolve().parent / "data" / "inputs.json")
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    config = data["generator"]
    assert data == build_dataset(config["base_seed"], config["include_empty_queries"]), "Regeneration differs"
    expected_ids = {
        f"n{n}_q{q}_{scenario}"
        for n in SIZES for q in QUERY_COUNTS for scenario in SCENARIOS
        if not (q == 1 and scenario == "mixed")
    }
    if config["include_empty_queries"]:
        expected_ids |= {f"n{n}_q0_empty" for n in SIZES}
    assert {case["case_id"] for case in data["cases"]} == expected_ids
    assert len(data["cases"]) == len(expected_ids)
    references = {}
    for array_id, entry in data["arrays"].items():
        values = entry["values"]
        assert len(values) == entry["n"]
        assert all(type(value) is int for value in values)
        assert array_hash(values) == entry["sha256"]
        references[array_id] = set(values)
        assert len(references[array_id]) == entry["distinct_count"] < entry["n"]
    modules = [importlib.import_module(name) for name in ("search_original", "search")]
    calls = 0
    for case in data["cases"]:
        entry = data["arrays"][case["array_id"]]
        assert case["n"] == entry["n"]
        queries = case["queries"]
        assert len(queries) == case["q"]
        expected = [value in references[case["array_id"]] for value in queries]
        assert case["expected"] == expected
        assert case["hit_count"] == sum(expected)
        assert case["hit_rate"] == (sum(expected) / len(queries) if queries else None)
        if case["scenario"] == "mixed":
            assert 0 < sum(expected) < len(queries)
        for module in modules:
            for name in METHODS:
                array = entry["values"].copy()
                given_queries = queries.copy()
                actual = getattr(module, name)(array, given_queries)
                assert isinstance(actual, list) and actual == expected, (case["case_id"], module.__name__, name)
                assert all(type(value) is bool for value in actual)
                assert array == entry["values"], "Array modified"
                assert given_queries == queries, "Queries modified"
                calls += 1
    print("PASS: fixed-seed regeneration, case coverage, lengths, hashes, duplicates, and hit rates.")
    print(f"PASS: {len(data['cases'])} cases x 2 versions x 3 methods = {calls} correct calls; inputs unchanged.")
    print("Validation only: no performance measurements collected.")


if __name__ == "__main__":
    main()

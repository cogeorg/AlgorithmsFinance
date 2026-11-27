"""Deterministic synthetic inputs for search tests and benchmarks."""

from __future__ import annotations

from random import Random


GENERATOR_VERSION = 2
DUPLICATE_POLICY = "sample_with_replacement_from_pool_max_1_array_size_div_3"


def generate_search_case(
    array_size: int,
    query_count: int,
    *,
    seed: int,
    hit_rate: float = 0.5,
) -> tuple[list[int], list[int]]:
    """Return an unsorted ID list and ordered queries of requested sizes.

    The generator intentionally draws IDs from a smaller value pool so that
    larger inputs contain duplicates. The requested hit count is rounded to the
    nearest representable integer, with halves rounded up. A local
    random-number generator prevents changes to global random state.
    """

    if array_size < 0:
        raise ValueError("array_size must be non-negative")
    if query_count < 0:
        raise ValueError("query_count must be non-negative")
    if not 0.0 <= hit_rate <= 1.0:
        raise ValueError("hit_rate must be between 0 and 1")

    random = Random(seed)
    value_pool_size = max(1, array_size // 3)
    ids = [random.randrange(value_pool_size) for _ in range(array_size)]

    # A one-query 50% scenario cannot literally be mixed. Rounding half up
    # selects one hit; the benchmark records both requested and realized rates.
    hit_count = int(query_count * hit_rate + 0.5) if ids else 0
    hits = [random.choice(ids) for _ in range(hit_count)]

    # IDs are always below value_pool_size, so this disjoint range guarantees
    # misses without repeatedly checking or retrying generated values.
    misses = [
        value_pool_size + random.randrange(max(1, query_count * 4))
        for _ in range(query_count - hit_count)
    ]

    queries = hits + misses
    random.shuffle(queries)
    return ids, queries

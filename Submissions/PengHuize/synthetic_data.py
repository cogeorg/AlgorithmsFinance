"""Generate reproducible synthetic inputs for membership-query benchmarks."""

import random
from typing import List, Tuple


def generate_synthetic_data(
    num_ids: int,
    num_queries: int,
    hit_rate: float = 0.5,
    seed: int = 0,
    allow_duplicates: bool = True,
) -> Tuple[List[int], List[int]]:
    """Return an integer ID array and ordered membership queries.

    ``hit_rate`` controls the requested share of queries sampled from the ID
    array. If the ID array is empty, every generated query is necessarily a
    miss. ``allow_duplicates`` records whether repeated IDs are permitted.
    A local random-number generator makes equal seeds reproducible and avoids
    changing Python's global random state.
    """
    if num_ids < 0:
        raise ValueError("num_ids must be non-negative")
    if num_queries < 0:
        raise ValueError("num_queries must be non-negative")
    if not 0.0 <= hit_rate <= 1.0:
        raise ValueError("hit_rate must be between 0 and 1")

    rng = random.Random(seed)
    value_bound = max(100, num_ids * 10)
    if allow_duplicates:
        ids = [
            rng.randint(-value_bound, value_bound)
            for _ in range(num_ids)
        ]
    else:
        population = range(-value_bound, value_bound + 1)
        ids = rng.sample(population, num_ids)

    requested_hits = round(num_queries * hit_rate)
    actual_hits = requested_hits if ids else 0
    queries = [rng.choice(ids) for _ in range(actual_hits)]

    # IDs never exceed value_bound, so these values are guaranteed misses.
    queries.extend(
        rng.randint(value_bound + 1, 2 * value_bound + 1)
        for _ in range(num_queries - actual_hits)
    )
    rng.shuffle(queries)

    return ids, queries

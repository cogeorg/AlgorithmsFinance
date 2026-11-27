"""Deterministic synthetic data generation, separate from algorithms and timing."""

from dataclasses import dataclass
import random
from typing import Literal


DuplicatePolicy = Literal["allow", "unique"]


@dataclass(frozen=True)
class SyntheticDataset:
    """One generated benchmark input and the settings needed to reproduce it."""

    ids: list[int]
    queries: list[int]
    seed: int
    requested_hit_rate: float
    duplicate_policy: DuplicatePolicy

    @property
    def actual_hit_rate(self) -> float:
        """Return the fraction of queries contained in the ID array."""
        if not self.queries:
            return 0.0
        id_set = set(self.ids)
        return sum(query in id_set for query in self.queries) / len(self.queries)


def generate_synthetic_data(
    n: int,
    q: int,
    hit_rate: float,
    duplicate_policy: DuplicatePolicy,
    seed: int,
) -> SyntheticDataset:
    """Generate reproducible IDs and ordered membership queries.

    ``hit_rate`` controls the number of present queries after rounding to the
    nearest integer. The query sequence is shuffled deterministically and must
    be consumed in the order returned.
    """
    if n < 0 or q < 0:
        raise ValueError("n and q must be non-negative")
    if not 0.0 <= hit_rate <= 1.0:
        raise ValueError("hit_rate must be between 0 and 1")
    if duplicate_policy not in ("allow", "unique"):
        raise ValueError("duplicate_policy must be 'allow' or 'unique'")

    rng = random.Random(seed)

    if duplicate_policy == "unique":
        ids = rng.sample(range(max(1, n * 10)), n)
    else:
        value_count = max(1, n // 2)
        ids = [rng.randrange(value_count) for _ in range(n)]

    present_count = round(q * hit_rate)
    if present_count and not ids:
        raise ValueError("cannot generate present queries from an empty ID array")

    present_queries = [rng.choice(ids) for _ in range(present_count)]
    id_set = set(ids)
    absent_queries: list[int] = []
    candidate = -1
    while len(absent_queries) < q - present_count:
        if candidate not in id_set:
            absent_queries.append(candidate)
        candidate -= 1

    queries = present_queries + absent_queries
    rng.shuffle(queries)
    return SyntheticDataset(ids, queries, seed, hit_rate, duplicate_policy)

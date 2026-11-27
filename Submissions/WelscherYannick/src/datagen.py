"""Synthetic data for the search lab.

This module only generates data. It contains no search or timing code and
uses its own random.Random instance, so it never touches global random state.

Policies (stored with every benchmark result):
    * IDs are distinct integers drawn from a universe of 10 * (n + q) + 10
      values centred on zero, so negative IDs occur.
    * Duplicate policy: int(n * duplicate_rate) of the n array entries repeat
      an earlier ID (at least one ID stays unique). The array is shuffled, so
      it is unsorted.
    * Hit policy: round(hit_rate * q) queries are drawn, with replacement, from
      the IDs in the array. The remaining queries are distinct IDs that are
      guaranteed to be absent. Query order is shuffled.
Same settings give the same data within one Python version; the random module
does not guarantee identical streams across versions.
"""

import random
from dataclasses import asdict, dataclass

DUPLICATE_POLICY = (
    "int(n * duplicate_rate) entries repeat an earlier id; at least one id stays "
    "unique; array shuffled"
)
HIT_POLICY = (
    "round(hit_rate * q) queries drawn with replacement from the array ids; "
    "remaining queries are distinct absent ids; queries shuffled"
)


@dataclass(frozen=True)
class GenSettings:
    n: int  # array entries, duplicates included
    q: int  # number of queries
    hit_rate: float  # fraction of queries whose id is present in the array
    duplicate_rate: float = 0.0  # fraction of the n entries repeating an earlier id
    seed: int = 0


def _validate(s: GenSettings) -> None:
    if s.n < 0 or s.q < 0:
        raise ValueError("n and q must be non-negative")
    if not 0.0 <= s.hit_rate <= 1.0:
        raise ValueError("hit_rate must be between 0 and 1")
    if not 0.0 <= s.duplicate_rate <= 1.0:
        raise ValueError("duplicate_rate must be between 0 and 1")
    if s.n == 0 and round(s.hit_rate * s.q) > 0:
        raise ValueError("an empty array cannot contain any queried id")


def generate(s: GenSettings) -> tuple[list[int], list[int]]:
    """Return (ids, queries) for the given settings."""
    _validate(s)
    rng = random.Random(s.seed)

    n_dup = min(int(s.n * s.duplicate_rate), s.n - 1) if s.n > 0 else 0
    n_unique = s.n - n_dup
    n_hit = round(s.hit_rate * s.q)
    n_miss = s.q - n_hit

    universe = 10 * (s.n + s.q) + 10
    offset = universe // 2
    pool = [x - offset for x in rng.sample(range(universe), n_unique + n_miss)]
    unique, absent = pool[:n_unique], pool[n_unique:]

    ids = unique + (rng.choices(unique, k=n_dup) if n_dup else [])
    rng.shuffle(ids)

    hits = rng.choices(unique, k=n_hit) if n_hit else []
    queries = hits + absent
    rng.shuffle(queries)
    return ids, queries


def describe(s: GenSettings, ids: list[int], queries: list[int]) -> dict:
    """Settings plus what was actually generated, for the saved metadata."""
    present = set(ids)
    hits = sum(1 for q in queries if q in present)
    return {
        **asdict(s),
        "n_actual": len(ids),
        "n_unique": len(present),
        "q_actual": len(queries),
        "hits": hits,
        "hit_rate_actual": hits / len(queries) if queries else None,
        "duplicate_policy": DUPLICATE_POLICY,
        "hit_policy": HIT_POLICY,
    }

"""Seeded synthetic data for the membership benchmarks (LAB_SPEC.md T5, I1-I4).

Kept separate from the algorithms (``membership/``) and the measurement code
(``bench/``). It uses no global random state: every call creates its own
``random.Random(seed)``, so the same arguments always give the same case.

Specification
-------------
``make_case(n, q, hit_rate, seed, duplicate_policy="allow", id_range=None)``

Input
    n                 Number of IDs in the array, n >= 0.
    q                 Number of queries, q >= 0.
    hit_rate          Requested share of present queries, 0.0 <= hit_rate <= 1.0.
                      1.0 = all-present, 0.0 = all-absent, 0.5 = mixed (decision Q2).
    seed              Integer seed for ``random.Random``.
    duplicate_policy  "allow": IDs drawn with replacement, duplicates occur naturally.
                      "unique": n distinct IDs (decision Q1).
    id_range          Number of possible base values. Default ``max(1, 2 * n)``.
                      For "unique" it must be >= n.

Output
    (ids, queries, meta)
    ids      list[int] of length n, in random (unsorted) order.
    queries  list[int] of length q, present and absent queries shuffled together.
    meta     dict with all settings plus realized values (see ``make_case``).

Construction
    Present IDs are even numbers ``2 * x`` with ``x`` in ``[0, id_range)``.
    Absent queries are odd numbers ``2 * x + 1`` from the same span, so they can
    never be in ``ids`` (guaranteed absent) and they fall *between* the present
    IDs, not only above the maximum. Otherwise binary search would always take
    the same branch on absent queries, which would bias the measurement.
    Present queries are drawn uniformly from the positions of ``ids``.
    The number of present queries is ``floor(hit_rate * q + 0.5)``.

Edge cases
    n == 0 with hit_rate > 0 and q > 0 raises ValueError (no present query is possible).
    q == 0 gives ``realized_hit_rate = None``.

Complexity
    O(n + q) time and memory ("unique" uses ``random.sample``, also O(n)).
"""

from __future__ import annotations

import math
import random
from typing import Any

GENERATOR_VERSION = "1"
DUPLICATE_POLICIES = ("allow", "unique")


def make_case(
    n: int,
    q: int,
    hit_rate: float,
    seed: int,
    duplicate_policy: str = "allow",
    id_range: int | None = None,
) -> tuple[list[int], list[int], dict[str, Any]]:
    """Generate one reproducible test case: ``(ids, queries, meta)``.

    ``meta`` holds the generator version, all settings (n, q, hit_rate, seed,
    duplicate_policy, id_range) and the realized values: ``n_distinct``,
    ``n_present_queries``, ``n_absent_queries`` and ``realized_hit_rate``.
    """
    if n < 0 or q < 0:
        raise ValueError("n and q must be >= 0")
    if not 0.0 <= hit_rate <= 1.0:
        raise ValueError("hit_rate must be in [0, 1]")
    if duplicate_policy not in DUPLICATE_POLICIES:
        raise ValueError(f"duplicate_policy must be one of {DUPLICATE_POLICIES}")
    if id_range is None:
        id_range = max(1, 2 * n)
    if id_range < 1:
        raise ValueError("id_range must be >= 1")
    if duplicate_policy == "unique" and id_range < n:
        raise ValueError("id_range must be >= n for duplicate_policy='unique'")

    rng = random.Random(seed)

    # 1. The ID array (even numbers).
    if duplicate_policy == "unique":
        base = rng.sample(range(id_range), n)
    else:
        base = [rng.randrange(id_range) for _ in range(n)]
    ids = [2 * x for x in base]

    # 2. How many queries are present.
    n_present = math.floor(hit_rate * q + 0.5)
    if n_present > 0 and n == 0:
        raise ValueError("cannot create present queries for an empty array (n == 0)")
    n_absent = q - n_present

    # 3. Present queries: copies of random array entries. Absent ones: odd numbers.
    present = [ids[rng.randrange(n)] for _ in range(n_present)]
    absent = [2 * rng.randrange(id_range) + 1 for _ in range(n_absent)]
    queries = present + absent
    rng.shuffle(queries)

    meta: dict[str, Any] = {
        "generator": "datagen.generator.make_case",
        "generator_version": GENERATOR_VERSION,
        "n": n,
        "q": q,
        "hit_rate": hit_rate,
        "seed": seed,
        "duplicate_policy": duplicate_policy,
        "id_range": id_range,
        "id_rule": "present IDs = 2*x, absent queries = 2*x+1, x in [0, id_range)",
        "n_distinct": len(set(ids)),
        "n_present_queries": n_present,
        "n_absent_queries": n_absent,
        "realized_hit_rate": (n_present / q) if q > 0 else None,
    }
    return ids, queries, meta

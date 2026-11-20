"""Synthetic data generator, kept separate from algorithms and measurement.

`make_ids` draws EVEN integers. `make_queries` works for ANY integer IDs: absent queries
are drawn outside the set of IDs and checked, so the hit rate of a batch is exact.

Revised after the Phase 2 audit by Bastian Bundschuh (see README, "Changes after the
Phase 2 audit"): explicit rounding (bug 1), input validation (bug 3) and absent queries
that are checked against the IDs (bug 4).
"""
import math
import random


def make_ids(n, seed, duplicates="none"):
    """n integer trade IDs in random order.

    duplicates="none":    all IDs distinct (sampled without replacement)
    duplicates="allowed": IDs sampled with replacement, so repeats occur
    """
    if n < 0:
        raise ValueError("n must be >= 0")
    rng = random.Random(seed)
    if duplicates == "none":
        return [2 * k for k in rng.sample(range(10 * n + 10), n)]
    if duplicates == "allowed":
        return [2 * rng.randrange(n + 1) for _ in range(n)]
    raise ValueError("duplicates must be 'none' or 'allowed'")


def present_count(q, hit_rate):
    """Number of present queries: q * hit_rate rounded HALF UP.

    Python's round() rounds halves to the even number (round(0.5) == 0), which made
    q = 1, hit rate 0.5 an all-absent batch. Rounding half up gives 1 present query for
    q = 1 and 2 of 3 for q = 3.
    """
    return math.floor(q * hit_rate + 0.5)


def make_queries(ids, q, hit_rate, seed):
    """Exactly q queries; present_count(q, hit_rate) are in ids, the rest are not.

    Present queries are copies of IDs; absent queries are integers checked to be missing
    from ids. The order of present and absent queries is shuffled with the same seed.
    """
    if q < 0:
        raise ValueError("q must be >= 0")
    if not 0 <= hit_rate <= 1:
        raise ValueError("hit_rate must be between 0 and 1")
    rng = random.Random(seed + 1)
    n_hit = present_count(q, hit_rate)
    if n_hit > 0 and not ids:
        raise ValueError("cannot draw present queries from an empty array")
    present = [rng.choice(ids) for _ in range(n_hit)]

    taken = set(ids)
    lo = (min(ids) if ids else 0) - q - 1
    hi = (max(ids) if ids else 0) + q + 1      # at least 2q + 2 integers outside the IDs
    absent = []
    while len(absent) < q - n_hit:
        x = rng.randint(lo, hi)
        if x not in taken:
            absent.append(x)
    queries = present + absent
    rng.shuffle(queries)
    return queries

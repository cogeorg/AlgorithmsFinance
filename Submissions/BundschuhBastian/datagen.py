"""Synthetic data for the membership lab. Only generates data: no algorithms, no timing.

generate(n, q, hit_rate, duplicates, seed) -> Dataset

hit_rate (share of queries whose ID is in the array):
    "all-present"  every query is in the array
    "all-absent"   no query is in the array
    "mixed"        (q + 1) // 2 queries are present, the rest absent (about half;
                   for q = 1 the single query is present)
duplicates (how often an ID repeats in the array):
    "none"   all n IDs are different
    "some"   about 90 % of the entries are different IDs (ceil(0.9 n) distinct)
    "many"   about 10 % of the entries are different IDs (ceil(0.1 n) distinct)

The array is in random order (not sorted). Present queries are copies of IDs from the
array. Absent queries are checked to be missing from the array and lie both inside
and outside the range of the array. Query order is random.
Same arguments -> identical data (own random.Random(seed); global random state unused).
"""
import math
import random
from dataclasses import asdict, dataclass

HIT_RATES = ("all-present", "all-absent", "mixed")
DUPLICATE_POLICIES = {"none": 1.0, "some": 0.9, "many": 0.1}   # share of distinct IDs


@dataclass(frozen=True)
class Dataset:
    ids: list
    queries: list
    expected: list      # correct answer per query, computed once with a set
    settings: dict      # n, q, hit_rate, duplicates, seed, id_universe


def _present_count(q, hit_rate):
    if hit_rate == "all-present":
        return q
    if hit_rate == "all-absent":
        return 0
    return (q + 1) // 2


def generate(n, q, hit_rate="mixed", duplicates="none", seed=0):
    if n < 0 or q < 0:
        raise ValueError("n and q must be >= 0")
    if hit_rate not in HIT_RATES:
        raise ValueError(f"hit_rate must be one of {HIT_RATES}")
    if duplicates not in DUPLICATE_POLICIES:
        raise ValueError(f"duplicates must be one of {tuple(DUPLICATE_POLICIES)}")
    present = _present_count(q, hit_rate)
    if present > 0 and n == 0:
        raise ValueError("cannot ask for present queries when n = 0")

    rng = random.Random(seed)
    universe = 10 * n + 10                      # IDs are drawn from 0 .. universe-1
    distinct = math.ceil(DUPLICATE_POLICIES[duplicates] * n)
    base = rng.sample(range(universe), distinct)            # distinct IDs
    ids = base + [rng.choice(base) for _ in range(n - distinct)]   # repeats
    rng.shuffle(ids)

    id_set = set(ids)
    queries = [rng.choice(ids) for _ in range(present)]
    while len(queries) < q:                     # absent: also below 0 and above universe
        candidate = rng.randrange(-universe, 2 * universe)
        if candidate not in id_set:
            queries.append(candidate)
    rng.shuffle(queries)

    expected = [x in id_set for x in queries]
    settings = {"n": n, "q": q, "hit_rate": hit_rate, "duplicates": duplicates,
                "seed": seed, "id_universe": universe}
    return Dataset(ids, queries, expected, settings)


def settings_dict(dataset):
    """Plain dict copy of the settings, for saving next to measurements."""
    return asdict(dataset)["settings"]

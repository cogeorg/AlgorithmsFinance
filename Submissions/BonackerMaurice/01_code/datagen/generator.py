"""Synthetic integer-ID data for tests and benchmarks.

Kept separate from the algorithms and from the measurement code.

Design:
- IDs are drawn from ``range(id_space)`` with ``id_space = id_space_factor * n``.
  ``duplicate_policy="allow"`` draws with replacement (duplicates occur);
  ``"unique"`` draws without replacement.
- The array depends only on (seed, n, duplicate_policy, id_space_factor), so every
  query count and scenario for the same n uses the *identical* array.
- Queries: exactly ``round_half_up(q * target_hit_rate)`` present queries, placed
  by *first occurrence* (where a linear scan stops): the j-th of k hits is the
  first distinct ID whose first occurrence is at or after position
  ``(j + 0.5) * n / k``. Hits are therefore spread evenly over the array, the
  average scan for a hit is about n/2, and a q = 1 result does not hinge on one
  random draw. ``mean_first_hit_frac`` records the realized value. Absent queries
  are drawn uniformly from the IDs in ``range(id_space)`` that are not in the
  array. The query order is shuffled.
- ``random.Random`` seeded with a string does not depend on PYTHONHASHSEED and is
  deterministic for a given Python version. Python does not promise that
  ``randrange``/``sample``/``shuffle`` stay identical across versions, so every
  dataset's SHA-256 checksums are saved in ``datasets.csv`` for verification.
- IDs are dense small integers (< 2^30): a best case for hashing (no collisions)
  and for CPython's small-int comparisons. Documented in the README.

CLI (inspect one dataset)::

    python -m datagen.generator --n 1000 --q 100 --scenario mixed [--out data.json]
"""
import argparse
import bisect
import hashlib
import json
import random
from dataclasses import asdict, dataclass

SCENARIOS = {"all_present": 1.0, "all_absent": 0.0, "mixed": 0.5}
DUPLICATE_POLICIES = ("allow", "unique")


@dataclass(frozen=True)
class DatasetSpec:
    n: int
    q: int
    scenario: str
    seed: int = 2026
    duplicate_policy: str = "allow"
    id_space_factor: int = 2

    @property
    def target_hit_rate(self) -> float:
        return SCENARIOS[self.scenario]

    @property
    def id_space(self) -> int:
        return self.id_space_factor * self.n

    @property
    def dataset_id(self) -> str:
        return f"n{self.n}_q{self.q}_{self.scenario}"

    def validate(self) -> None:
        if self.n < 0 or self.q < 0:
            raise ValueError("n and q must be >= 0")
        if self.scenario not in SCENARIOS:
            raise ValueError(f"scenario must be one of {list(SCENARIOS)}")
        if self.duplicate_policy not in DUPLICATE_POLICIES:
            raise ValueError(f"duplicate_policy must be one of {DUPLICATE_POLICIES}")
        if self.id_space_factor < 2:
            raise ValueError("id_space_factor must be >= 2 so absent IDs always exist")
        if self.n == 0 and present_count(self.q, self.target_hit_rate) > 0:
            raise ValueError("an empty array cannot produce present queries")


@dataclass(frozen=True)
class Dataset:
    spec: DatasetSpec
    ids: list
    queries: list
    present_queries: int

    @property
    def realized_hit_rate(self) -> float:
        return self.present_queries / self.spec.q if self.spec.q else 0.0

    @property
    def distinct_values(self) -> int:
        return len(set(self.ids))

    @property
    def mean_first_hit_frac(self):
        """Mean index of each present query's first occurrence, as a fraction of n
        (what a linear scan pays for hits). None if there are no present queries."""
        first = {}
        for i, value in enumerate(self.ids):
            first.setdefault(value, i)
        hits = [first[x] for x in self.queries if x in first]
        return sum(hits) / len(hits) / len(self.ids) if hits else None

    @property
    def ids_sha256(self) -> str:
        return checksum(self.ids)

    @property
    def queries_sha256(self) -> str:
        return checksum(self.queries)

    def summary(self) -> dict:
        """One row of 02_results/<run_id>/datasets.csv."""
        s = self.spec
        return {
            "dataset_id": s.dataset_id, "n": s.n, "q": s.q, "scenario": s.scenario,
            "target_hit_rate": s.target_hit_rate, "present_queries": self.present_queries,
            "realized_hit_rate": self.realized_hit_rate,
            "mean_first_hit_frac": self.mean_first_hit_frac,
            "duplicate_policy": s.duplicate_policy, "id_space": s.id_space,
            "distinct_values": self.distinct_values, "seed": s.seed,
            "array_sha256": self.ids_sha256, "queries_sha256": self.queries_sha256,
        }


def present_count(q: int, hit_rate: float) -> int:
    """Number of present queries: q * hit_rate rounded half up (q=1, 0.5 -> 1)."""
    return int(q * hit_rate + 0.5)


def checksum(values) -> str:
    return hashlib.sha256(",".join(map(str, values)).encode()).hexdigest()


def make_ids(spec: DatasetSpec) -> list:
    rng = random.Random(f"ids|{spec.seed}|{spec.n}|{spec.duplicate_policy}|{spec.id_space_factor}")
    if spec.duplicate_policy == "allow":
        return [rng.randrange(spec.id_space) for _ in range(spec.n)]
    return rng.sample(range(spec.id_space), spec.n)


def make_queries(spec: DatasetSpec, ids: list) -> tuple:
    rng = random.Random(f"queries|{spec.seed}|{spec.n}|{spec.q}|{spec.scenario}"
                        f"|{spec.duplicate_policy}|{spec.id_space_factor}")
    hits = present_count(spec.q, spec.target_hit_rate)
    first_pos, first_val, present = [], [], set()  # distinct IDs by first occurrence
    for i, value in enumerate(ids):
        if value not in present:
            present.add(value)
            first_pos.append(i)
            first_val.append(value)
    queries = []
    for j in range(hits):  # stratified first-hit positions
        k = bisect.bisect_left(first_pos, (j + 0.5) * len(ids) / hits)
        queries.append(first_val[min(k, len(first_val) - 1)])
    while len(queries) < spec.q:  # rejection sampling; >= half of id_space is absent
        candidate = rng.randrange(spec.id_space) if spec.id_space else rng.randrange(1_000_000)
        if candidate not in present:
            queries.append(candidate)
    rng.shuffle(queries)
    return queries, hits


def generate(spec: DatasetSpec) -> Dataset:
    spec.validate()
    ids = make_ids(spec)
    queries, hits = make_queries(spec, ids)
    return Dataset(spec, ids, queries, hits)


def main(argv=None):
    p = argparse.ArgumentParser(description="Generate one synthetic dataset.")
    p.add_argument("--n", type=int, required=True)
    p.add_argument("--q", type=int, required=True)
    p.add_argument("--scenario", choices=list(SCENARIOS), required=True)
    p.add_argument("--seed", type=int, default=2026)
    p.add_argument("--duplicate-policy", choices=DUPLICATE_POLICIES, default="allow")
    p.add_argument("--id-space-factor", type=int, default=2)
    p.add_argument("--out", help="write {spec, summary, ids, queries} as JSON")
    a = p.parse_args(argv)
    d = generate(DatasetSpec(a.n, a.q, a.scenario, a.seed, a.duplicate_policy, a.id_space_factor))
    print(json.dumps(d.summary(), indent=2))
    if a.out:
        with open(a.out, "w") as f:
            json.dump({"spec": asdict(d.spec), "summary": d.summary(),
                       "ids": d.ids, "queries": d.queries}, f)
        print(f"wrote {a.out}")


if __name__ == "__main__":
    main()

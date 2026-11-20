"""Independent correctness checks of Bastian's four methods and his data generator.

Expected answers come from Python's `x in ids`, not from his code.
Run:  python fuzz_methods.py      (writes logs/fuzz_methods.txt)
"""
import copy
import random

from _common import Report, import_target

membership, datagen = import_target()
R = Report("fuzz_methods")
rng = random.Random(20261120)
METHODS, PHASES = membership.METHODS, membership.PHASES


def expected(ids, queries):
    return [x in ids for x in queries]


# 1. Hand-picked edge cases from the specification (slides 56-57 and 66).
cases = [
    ([7, 11, 7], [11, 9, 7]),                 # slide example
    ([], [1, 2]), ([5], []), ([], []),        # empty array / queries
    ([5], [5, 4, 6]),                         # one entry
    ([3, 3, 3, 3], [3, 2, 4]),                # all entries equal
    ([9, 1, 8, 2, 7], [9, 7, 5]),             # unsorted, first and last position
    ([-7, 0, -3], [-7, 3, 0]),                # negative IDs
    ([10**30, -10**30, 0], [10**30, 10**30 + 1, -10**30]),   # very large integers
    ([1, 2], [2, 2, 1, 3, 2]),                # repeated queries, output order
]
for ids, queries in cases:
    for name, f in METHODS.items():
        a, b = list(ids), list(queries)
        out = f(a, b)
        R.check(out == expected(ids, queries) and a == ids and b == queries
                and all(type(v) is bool for v in out),
                f"{name} ids={ids} queries={queries} -> {out}")

# 2. Random differential test: 3,000 random inputs, every method, inputs unchanged,
#    and each answer phase leaves the prepared state unchanged when called twice.
bad = 0
for _ in range(3000):
    n = rng.randint(0, 40)
    lo = rng.choice([-10**30, -50, 0])
    hi = lo + rng.choice([3, 60, 10**31])
    ids = [rng.randint(lo, hi) for _ in range(n)]
    if n and rng.random() < 0.3:
        ids = [ids[0]] * n                         # many equal values
    queries = [rng.randint(lo - 2, hi + 2) for _ in range(rng.randint(0, 15))]
    if ids:
        queries += [rng.choice(ids) for _ in range(rng.randint(0, 3))]
    exp = expected(ids, queries)
    for name, f in METHODS.items():
        a, b = list(ids), list(queries)
        if f(a, b) != exp or a != ids or b != queries:
            bad += 1
        prepare, answer = PHASES[name]
        state = prepare(list(ids))
        before = copy.copy(state)
        if answer(state, queries) != exp or answer(state, queries) != exp or state != before:
            bad += 1
R.check(bad == 0, f"random differential test: 3000 inputs x 4 methods, {bad} mismatches")

# 3. Large input for the recursive version (recursion depth grows only with log n).
big = list(range(2_000_000))
R.check(METHODS["binary_v1"](big, [1_999_999, 0, -1, 2_000_000]) == [True, True, False, False],
        "binary_v1 on 2,000,000 sorted IDs (no recursion error)")

# 4. Data generator: sizes, exact hit counts, no duplicates for 'none', reproducible.
problems = 0
for _ in range(2000):
    n, q = rng.randint(0, 300), rng.randint(0, 50)
    hit = rng.choice(datagen.HIT_RATES)
    dup = rng.choice(["none", "some", "many"])
    seed = rng.randint(0, 10**6)
    try:
        d = datagen.generate(n, q, hit, dup, seed)
    except ValueError:
        if not (n == 0 and q > 0 and hit != "all-absent"):
            problems += 1
        continue
    s = set(d.ids)
    want = {"all-present": q, "all-absent": 0, "mixed": (q + 1) // 2}[hit]
    if len(d.ids) != n or len(d.queries) != q or sum(x in s for x in d.queries) != want:
        problems += 1
    if dup == "none" and len(s) != n:
        problems += 1
    d2 = datagen.generate(n, q, hit, dup, seed)
    if d2.ids != d.ids or d2.queries != d.queries:
        problems += 1
R.check(problems == 0, f"datagen: 2000 random settings, {problems} problems "
        "(sizes, exact hit count, no duplicates for 'none', same output for same seed)")

# 5. Observation outside the specification: a one-shot iterator as the ID array.
gen_out = {name: f(iter([3, 1, 2]), [2, 3]) for name, f in METHODS.items()}
R.note(f"outside the spec (input is not an array): iterator ids [3, 1, 2], queries [2, 3] "
       f"-> {gen_out}; expected [True, True]")

R.save()

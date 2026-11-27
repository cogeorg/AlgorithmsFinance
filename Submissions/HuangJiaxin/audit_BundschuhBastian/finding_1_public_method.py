"""Finding 1: the claim "public method == answer(prepare(ids), queries)" does not hold
for binary_v2 when the query list is empty.

Bastian's membership.py (module docstring) and REVISIONS.md ("Refactor note") state that
every public method is exactly answer(prepare(ids), queries), "so the tested code is the
timed code". binary_search_iterative (binary_v2) returns [] before calling prepare when
there are no queries. This script shows it, and also times that case, which his
benchmark grid (q in {1, 100}) never measures.

Run:  python finding_1_public_method.py      (writes logs/finding_1_public_method.txt)
"""
import random
import statistics
import time

from _common import Report, import_target

membership, _ = import_target()
R = Report("finding_1_public_method")

# 1. Count calls of the shared preparation function (sorting a copy).
calls = {"n": 0}
original_prepare = membership._binary_prepare


def counting_prepare(ids):
    calls["n"] += 1
    return original_prepare(ids)


membership._binary_prepare = counting_prepare
prepare_v2, answer_v2 = membership.PHASES["binary_v2"]
try:
    ids = [5, 3, 9]
    for label, run in [
        ("public method binary_v2(ids, [])", lambda: membership.binary_search_iterative(ids, [])),
        ("answer(prepare(ids), []) via PHASES", lambda: answer_v2(membership._binary_prepare(ids), [])),
        ("public method binary_v1(ids, [])", lambda: membership.binary_search_recursive(ids, [])),
    ]:
        calls["n"] = 0
        out = run()
        R.note(f"{label}: output {out}, preparation calls {calls['n']}")
    calls["n"] = 0
    membership.binary_search_iterative(ids, [])
    R.check(calls["n"] == 1, "binary_v2 public method runs prepare like answer(prepare(ids), queries) "
            f"for an empty query list (observed {calls['n']} calls)")
finally:
    membership._binary_prepare = original_prepare

# 2. The same claim for every method and q >= 1: outputs agree (this part holds).
rng = random.Random(1)
ok = True
for name, method in membership.METHODS.items():
    prepare, answer = membership.PHASES[name]
    for _ in range(200):
        ids = [rng.randint(0, 30) for _ in range(rng.randint(0, 20))]
        queries = [rng.randint(0, 30) for _ in range(rng.randint(1, 10))]
        ok &= method(ids, queries) == answer(prepare(ids), queries)
R.check(ok, "for q >= 1, every public method gives the same output as answer(prepare(ids), queries)")

# 3. Outside the specification: v1 and v2 react differently to unsortable input.
for name in ["binary_v1", "binary_v2"]:
    try:
        out = membership.METHODS[name]([1, "a"], [])
        R.note(f"outside the spec: {name}([1, 'a'], []) -> {out}")
    except TypeError as e:
        R.note(f"outside the spec: {name}([1, 'a'], []) -> TypeError: {e}")

# 4. Time the case his benchmark does not cover: n = 100,000 IDs, q = 0 queries.
ids = random.Random(20260).sample(range(1_000_010), 100_000)
for name in ["binary_v1", "binary_v2"]:
    f = membership.METHODS[name]
    f(ids, [])                                   # warm-up
    reps = []
    for _ in range(5):
        t0 = time.perf_counter()
        f(ids, [])
        reps.append(time.perf_counter() - t0)
    R.note(f"timing q = 0, n = 100,000: {name} median {statistics.median(reps) * 1e3:.4f} ms "
           f"(5 repeats: {', '.join(f'{r * 1e3:.4f}' for r in reps)} ms)")

R.save()

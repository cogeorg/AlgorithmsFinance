"""B1: LaviBen's preparation timing includes freeing the previous algorithm's state.

Usage (from Submissions/WelscherYannick):
    python3 audit/reproducers/repro_b1_preparation_includes_freeing.py PATH/TO/Submissions/LaviBen

PATH must be a checkout of the audited commit 4777c48. The audited code is
imported unchanged; nothing in it is edited.

Part 1 (deterministic, decides the exit code): benchmark._measure_fixed_inputs
is called unchanged with two test-double algorithms. Algorithm A builds a state
that takes 5 ms to free; algorithm B's prepare returns its input and does no
work. If the measurement were correct, B's preparation time would be far below
1 ms. It is not: whenever B follows A, B is charged the 5 ms of freeing A's
state, because `prepared` still holds A's state when B's timer starts
(benchmark.py lines 319-322).

Part 2 (realistic, for scale): the same pattern with LaviBen's real prepare
functions on his own generated data.

Exit code 1 means the bug is present.
"""

import gc
import statistics
import sys
import time
from time import perf_counter_ns

if len(sys.argv) != 2:
    sys.exit(__doc__)
sys.path.insert(0, sys.argv[1])

import benchmark as bm  # noqa: E402  (LaviBen's module, unchanged)
from search_algorithms import prepare_binary, prepare_hash_set, prepare_linear  # noqa: E402
from synthetic_data import generate_search_case  # noqa: E402

FREE_DELAY_S = 0.005


class SlowToFree:
    def __del__(self):
        time.sleep(FREE_DELAY_S)


def no_hits(state, queries):
    return [False] * len(queries)


# --- Part 1: deterministic --------------------------------------------------------
fixed_inputs = bm._build_fixed_inputs([10], [1], ["all_absent"], base_seed=1)
original_algorithms = bm.ALGORITHMS
bm.ALGORITHMS = (
    bm.AlgorithmSpec("A: state takes 5 ms to free", "test", lambda ids: SlowToFree(), no_hits),
    bm.AlgorithmSpec("B: prepare does nothing", "test", lambda ids: ids, no_hits),
)
try:
    raw = bm._measure_fixed_inputs(fixed_inputs, repeats=4)
finally:
    bm.ALGORITHMS = original_algorithms

print("Part 1: LaviBen's _measure_fixed_inputs, unchanged, with two test doubles")
print(f"{'repeat':>6} {'pos':>3}  {'algorithm':<30} {'preparation':>12}")
b_times = []
for r in raw:
    print(f"{r.repeat:>6} {r.order_position:>3}  {r.algorithm:<30} {r.preparation_ns / 1e6:>9.3f} ms")
    if r.algorithm.startswith("B"):
        b_times.append(r.preparation_ns)
worst = max(b_times) / 1e6
print(f"\nExpected: B's preparation far below 1 ms (it does nothing).")
print(f"Actual:   B's preparation up to {worst:.3f} ms, i.e. the {FREE_DELAY_S * 1e3:.0f} ms of freeing A's state.")

# --- Part 2: realistic scale ------------------------------------------------------
def timed_like_benchmark(previous_state, ids, release_first):
    prepared = previous_state
    del previous_state
    if release_first:
        prepared = None  # proposed fix: release before the timer starts
    gc.disable()
    start = perf_counter_ns()
    prepared = prepare_linear(ids)  # noqa: F841  (returns ids, no work)
    elapsed = perf_counter_ns() - start
    gc.enable()
    return elapsed


print("\nPart 2: LaviBen's prepare_linear (a no-op) timed as in benchmark.py, median of 15")
for n in (1_000, 10_000, 100_000):
    ids, _ = generate_search_case(n, 1, seed=2026, hit_rate=1.0)
    ids = tuple(ids)
    for label, make in (("sorted copy", prepare_binary), ("hash set", prepare_hash_set)):
        as_is = statistics.median(timed_like_benchmark(make(ids), ids, False) for _ in range(15))
        fixed = statistics.median(timed_like_benchmark(make(ids), ids, True) for _ in range(15))
        print(f"  n={n:>7,} after {label:<11}: as benchmarked {as_is:>9,.0f} ns"
              f" | previous state released first {fixed:>5,.0f} ns")

if worst >= 1.0:
    print("\nBUG PRESENT: preparation time includes freeing the previous algorithm's state.")
    sys.exit(1)
print("\nBug not reproduced.")

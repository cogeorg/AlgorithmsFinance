"""Run WelscherYannick's contract checks against LaviBen's methods (code unchanged).

Usage: python3 run_contract_checks.py PATH/TO/LaviBen PATH/TO/WelscherYannick
"""
import sys, traceback
ben, mine = sys.argv[1], sys.argv[2]
sys.path[:0] = [ben, mine + "/src", mine + "/tests"]
import search_algorithms as B
from interface import Method
from contract import ALL_CHECKS

methods = [
    Method("linear", B.prepare_linear, B.linear_query_batch),
    Method("binary_recursive_v1", B.prepare_binary, B.binary_recursive_query_batch),
    Method("binary_iterative_v2", B.prepare_binary, B.binary_iterative_query_batch),
    Method("hash_set", B.prepare_hash_set, B.hash_set_query_batch),
]
failures = 0
for m in methods:
    for check in ALL_CHECKS:
        try:
            check(m)
        except Exception as e:
            failures += 1
            msg = str(e).splitlines()[0] if str(e) else type(e).__name__
            print(f"FAIL {m.name:<20} {check.__name__}: {msg}")
print(f"{len(methods) * len(ALL_CHECKS) - failures} passed, {failures} failed "
      f"({len(ALL_CHECKS)} checks x {len(methods)} methods)")
# The public one-call functions too
for name in ("linear_search", "binary_search_recursive_v1", "binary_search", "hash_set_membership"):
    f = getattr(B, name)
    ids = [5, 3, 5, 1]; before = list(ids)
    assert f(ids, [3, 9, 5]) == [True, False, True] and ids == before, name
print("public functions: spec example and unchanged input OK")

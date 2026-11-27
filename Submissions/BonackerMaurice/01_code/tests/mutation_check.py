"""Check that the test suite detects *wrong* behaviour, not only missing behaviour.

Each mutant swaps one function of one registered method for a deliberately
buggy version (in memory only; no source file is changed), runs
tests/test_search.py in a fresh process, and reports whether the suite
caught it ("killed"). A surviving mutant means a missing test.

Rule violations that only show in the source code (for example using `in` on a
list inside linear search) cannot be injected at runtime; they are guarded by
the AST test in tests/test_search.py instead.

    python -m tests.mutation_check
"""
import re
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent


def _binary_upper_bound(sorted_ids, queries):  # `<=` instead of `<`: lands after x
    out = []
    for x in queries:
        lo, hi = 0, len(sorted_ids)
        while lo < hi:
            mid = (lo + hi) // 2
            if sorted_ids[mid] <= x:
                lo = mid + 1
            else:
                hi = mid
        out.append(lo < len(sorted_ids) and sorted_ids[lo] == x)
    return out


def _binary_secretly_linear(sorted_ids, queries):  # mid = lo: correct answers, O(n) cost
    out = []
    for x in queries:
        lo, hi = 0, len(sorted_ids)
        while lo < hi:
            mid = lo
            if sorted_ids[mid] < x:
                lo = mid + 1
            else:
                hi = mid
        out.append(lo < len(sorted_ids) and sorted_ids[lo] == x)
    return out


def _linear_sorts_input(ids):  # "prepares" by sorting the caller's array in place
    ids.sort()
    return ids


MUTANTS = {
    "binary_v2 prepare forgets to sort": ("binary_v2", "prepare", lambda ids: list(ids)),
    "binary_v2 uses <= (upper bound)": ("binary_v2", "query", _binary_upper_bound),
    "binary_v2 is secretly linear (mid = lo)": ("binary_v2", "query", _binary_secretly_linear),
    "hash prepares a list instead of a set": ("hash_v1", "prepare", lambda ids: list(ids)),
    "binary_v1 recursion skips mid+1..hi": (
        "binary_v1", "query",
        lambda a, qs: [bool(a) and a[len(a) // 2] == q or q in a[:len(a) // 2] for q in qs]),
    "linear_v1 prepare sorts caller's array": ("linear_v1", "prepare", _linear_sorts_input),
    "linear_v2 skips the last element": (
        "linear_v2", "query", lambda d, qs: [any(v == q for v in d[:-1]) for q in qs]),
    "linear_v2 answers unique queries only": (
        "linear_v2", "query", lambda d, qs: [any(v == q for v in d) for q in dict.fromkeys(qs)]),
    "hash answers in sorted query order": (
        "hash_v1", "query", lambda s, qs: [q in s for q in sorted(qs)]),
    "hash returns 1/0 instead of True/False": (
        "hash_v1", "query", lambda s, qs: [int(q in s) for q in qs]),
}


def apply(name: str) -> None:
    """Install one mutant into the registry (called inside the child process)."""
    from search_algos import METHODS
    key, attribute, replacement = MUTANTS[name]
    method = next(m for m in METHODS if m.key == key)
    object.__setattr__(method, attribute, replacement)  # Method is a frozen dataclass


def main() -> int:
    survivors = 0
    for name in MUTANTS:
        code = ("import sys, pytest, tests.mutation_check as mc; "
                f"mc.apply({name!r}); "
                "sys.exit(pytest.main(['-q', '--no-header', '-p', 'no:cacheprovider', "
                "'tests/test_search.py']))")
        proc = subprocess.run([sys.executable, "-c", code], cwd=PROJECT_DIR,
                              capture_output=True, text=True)
        lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
        failed = re.search(r"(\d+) failed", lines[-1] if lines else "")
        killed = proc.returncode != 0 and failed
        survivors += not killed
        print(f"{'KILLED  ' if killed else 'SURVIVED'} {name:<42} "
              f"({failed.group(1) if failed else 0} failing tests)")
    print(f"\n{len(MUTANTS) - survivors}/{len(MUTANTS)} mutants killed")
    return 1 if survivors else 0


if __name__ == "__main__":
    sys.exit(main())

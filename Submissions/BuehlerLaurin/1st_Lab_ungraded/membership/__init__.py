"""Membership queries: shared interface and registry of all methods and versions.

Specification (LAB_SPEC.md F1-F6, decisions Q4-Q5)
---------------------------------------------------
Input
    ids      A sequence of ints (the "ID array"). May be empty, unsorted, contain
             duplicates and negative values. It is never modified (F4).
    queries  A sequence of ints. May be empty and contain repeats.
Output
    A new ``list[bool]`` with ``len(queries)`` elements. Element ``i`` is ``True``
    if and only if ``queries[i]`` occurs in ``ids`` (F3). Order equals query order.

Two phases per method, so that preparation can be timed on its own (I5):
    prepare(ids) -> state
        linear: the input itself, no copy               O(1)
        binary: a sorted copy of the input              O(n log n)
        hash:   a set built from the input              expected O(n)
    query(state, queries) -> list[bool]
        linear: O(n) per query, binary: O(log n) per query (v2), hash: expected O(1)
        per query.
A state can be queried any number of times. ``query`` never changes the state.

Registry
    METHODS maps ``(method, version)`` to a :class:`MethodSpec`, with
    method in {"linear", "binary", "hash"} and version in {"original", "revised"}.
    Tests and benchmarks iterate over METHODS, so every method and version is
    checked by the same test suite (F5) and measured on the same inputs (I3).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from membership import original, revised

PrepareFn = Callable[[Sequence[int]], Any]
QueryFn = Callable[[Any, Sequence[int]], list[bool]]


@dataclass(frozen=True)
class MethodSpec:
    """One method in one version: its name, version and two phase functions."""

    method: str
    version: str
    prepare: PrepareFn
    query: QueryFn

    @property
    def label(self) -> str:
        """Short name for test IDs, tables and plots, e.g. ``"binary-revised"``."""
        return f"{self.method}-{self.version}"

    def run(self, ids: Sequence[int], queries: Sequence[int]) -> list[bool]:
        """Prepare and query in one call (convenience; not used for timing)."""
        return self.query(self.prepare(ids), queries)


METHODS: dict[tuple[str, str], MethodSpec] = {
    ("linear", "original"): MethodSpec(
        "linear", "original", original.linear_prepare, original.linear_query
    ),
    ("binary", "original"): MethodSpec(
        "binary", "original", original.binary_prepare, original.binary_query
    ),
    ("hash", "original"): MethodSpec(
        "hash", "original", original.hash_prepare, original.hash_query
    ),
    ("linear", "revised"): MethodSpec(
        "linear", "revised", revised.linear_prepare, revised.linear_query
    ),
    ("binary", "revised"): MethodSpec(
        "binary", "revised", revised.binary_prepare, revised.binary_query
    ),
    ("hash", "revised"): MethodSpec(
        "hash", "revised", revised.hash_prepare, revised.hash_query
    ),
}

# Both v2 binary-search candidates (decision Q3). They are not separate versions in the
# benchmark grid; they exist so that the test suite checks both and
# bench/binary_variants.py can measure which one becomes ``revised.binary_query``.
BINARY_V2_CANDIDATES: dict[str, MethodSpec] = {
    "classic": MethodSpec(
        "binary", "revised-classic", revised.binary_prepare, revised.binary_query_classic
    ),
    "lower_bound": MethodSpec(
        "binary",
        "revised-lower_bound",
        revised.binary_prepare,
        revised.binary_query_lower_bound,
    ),
}

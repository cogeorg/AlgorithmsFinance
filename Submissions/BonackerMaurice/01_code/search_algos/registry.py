"""Registry of all search methods and versions.

Every method is split into ``prepare(ids) -> state`` and
``query(state, queries) -> list[bool]`` so the benchmarks can time
preparation and the query batch separately. ``Method.__call__`` is the
public entry point: it validates the input, then prepares and queries.
"""
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from . import binary, hashset, linear
from .validation import check_ids

Prepare = Callable[[Sequence[int]], Any]
Query = Callable[[Any, Sequence[int]], list]


@dataclass(frozen=True)
class Method:
    method: str        # "linear" | "binary" | "hash"
    version: str       # "v1" (original) | "v2" (revised)
    role: str          # "original" | "revised" | "only"
    label: str
    description: str
    prepare: Prepare
    query: Query

    @property
    def key(self) -> str:
        return f"{self.method}_{self.version}"

    def __call__(self, ids: Sequence[int], queries: Sequence[int]) -> list:
        check_ids(ids, "ids")
        check_ids(queries, "queries")
        return self.query(self.prepare(ids), queries)


METHODS = (
    Method("linear", "v1", "original", "LinearSearch v1",
           "Defensive copy of the input, then an index-based while-loop scan per query.",
           linear.prepare_v1, linear.query_v1),
    Method("linear", "v2", "revised", "LinearSearch v2",
           "No copy (the scan never mutates the input); direct for-loop iteration per query.",
           linear.prepare_v2, linear.query_v2),
    Method("binary", "v1", "original", "BinarySearch v1",
           "sorted() copy, then recursive binary search with early exit on equality.",
           binary.prepare, binary.query_v1),
    Method("binary", "v2", "revised", "BinarySearch v2",
           "sorted() copy, then iterative lower-bound binary search (no recursion).",
           binary.prepare, binary.query_v2),
    Method("hash", "v1", "only", "HashSet",
           "set() of the input, then one membership test per query.",
           hashset.prepare, hashset.query),
)

# Version of each method that represents the submission's current state.
CURRENT = {"linear": "v2", "binary": "v2", "hash": "v1"}


def get_method(method: str, version: str | None = None) -> Method:
    """Return a registered method; ``version=None`` means the current version."""
    version = version or CURRENT[method]
    for m in METHODS:
        if m.method == method and m.version == version:
            return m
    raise KeyError(f"unknown method/version: {method} {version}")


def current_methods() -> list:
    return [get_method(name) for name in CURRENT]

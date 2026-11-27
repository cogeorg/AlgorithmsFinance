"""Shared contract for every search method in this lab (specification, slide 57).

Input
    ids      sequence of ints. May be empty, unsorted, and contain duplicates.
    queries  sequence of ints. May be empty and contain repeats.

Output
    A list of bool with len(queries) entries. Entry i is True exactly when
    queries[i] occurs in ids. The order of the output follows the order of queries.

Rules
    * ids and queries are never modified (not sorted in place, not emptied).
    * query() never modifies the prepared state, so one state can serve many
      query batches and repeated calls give identical results.
    * The prepared state does not depend on later changes to ids: queries
      answer for ids as they were when prepare() was called.
    * Any sequence of ints is accepted (e.g. list or tuple), including ints
      beyond 64 bits; the result is always a list.

Each method is split into two stages so that preparation (sorting, building a
hash set) and the query batch can be timed separately (slide 60):

    state  = method.prepare(ids)
    result = method.query(state, queries)

contains_all() runs both stages and is the function that satisfies the
specification as a whole.
"""

from typing import Any, Callable, NamedTuple, Sequence


class Method(NamedTuple):
    name: str
    prepare: Callable[[Sequence[int]], Any]
    query: Callable[[Any, Sequence[int]], list[bool]]

    def contains_all(self, ids: Sequence[int], queries: Sequence[int]) -> list[bool]:
        return self.query(self.prepare(ids), queries)

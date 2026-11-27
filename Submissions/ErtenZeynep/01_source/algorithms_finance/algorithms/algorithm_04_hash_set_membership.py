"""Standard-library hash-set membership for ordered query batches."""

from __future__ import annotations

from collections.abc import Sequence


def prepare_hash_set(array: Sequence[int]) -> set[int]:
    """Build a fresh membership set without modifying the input array."""

    return set(array)


def query_hash_set_membership(
    prepared_set: set[int],
    queries: Sequence[int],
) -> list[bool]:
    """Return membership results in the original query order."""

    return [query in prepared_set for query in queries]


def hash_set_membership(
    array: Sequence[int],
    queries: Sequence[int],
) -> list[bool]:
    """Build a set, then return one Boolean per query."""

    prepared_set = prepare_hash_set(array)
    return query_hash_set_membership(prepared_set, queries)

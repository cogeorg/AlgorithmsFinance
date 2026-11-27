"""Manual Linear Search for ordered membership-query batches."""

from __future__ import annotations

from collections.abc import Sequence


def prepare_linear_search(array: Sequence[int]) -> Sequence[int]:
    """Return the read-only search input; Linear Search needs no preparation."""

    return array


def query_linear_search(
    prepared_array: Sequence[int],
    queries: Sequence[int],
) -> list[bool]:
    """Answer each query with a manual left-to-right scan."""

    results: list[bool] = []
    for query in queries:
        found = False
        for value in prepared_array:
            if value == query:
                found = True
                break
        results.append(found)
    return results


def linear_search(
    array: Sequence[int],
    queries: Sequence[int],
) -> list[bool]:
    """Return one Boolean per query without modifying either input sequence."""

    prepared_array = prepare_linear_search(array)
    return query_linear_search(prepared_array, queries)

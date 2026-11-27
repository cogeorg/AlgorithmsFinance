"""Revised searches: manual linear/binary procedures and library hash sets."""

try:
    from . import search_original
except ImportError:
    import search_original


def prepare_linear(ids):
    """Linear search only reads IDs, so no defensive copy is needed."""
    return ids


def query_linear(items, queries):
    answers = []
    for query in queries:
        found = False
        for item in items:
            if item == query:
                found = True
                break
        answers.append(found)
    return answers


def prepare_binary(ids):
    """sorted already creates a new list and leaves IDs unchanged."""
    return sorted(ids)


def query_binary(items, queries):
    answers = []
    for query in queries:
        left, right = 0, len(items) - 1
        found = False
        while left <= right:
            middle = (left + right) // 2
            value = items[middle]
            if value == query:
                found = True
                break
            if value < query:
                left = middle + 1
            else:
                right = middle - 1
        answers.append(found)
    return answers


def prepare_set(ids):
    """Set construction reads the input directly; an intermediate copy wastes memory."""
    return set(ids)


def query_set(items, queries):
    return [query in items for query in queries]


PREPARERS = {"linear": prepare_linear, "binary": prepare_binary, "set": prepare_set}
QUERIERS = {"linear": query_linear, "binary": query_binary, "set": query_set}


def linear_search(ids, queries):
    return query_linear(prepare_linear(ids), queries)


def binary_search(ids, queries):
    return query_binary(prepare_binary(ids), queries)


def set_search(ids, queries):
    return query_set(prepare_set(ids), queries)


SEARCH_METHODS = {"linear": linear_search, "binary": binary_search, "set": set_search}
VERSIONS = {
    "original": {"prepare": search_original.PREPARERS, "query": search_original.QUERIERS,
                 "batch": search_original.SEARCH_METHODS},
    "revised": {"prepare": PREPARERS, "query": QUERIERS, "batch": SEARCH_METHODS},
}
VERSIONED_METHODS = {f"{version}/{name}": method
                     for version, methods in VERSIONS.items()
                     for name, method in methods["batch"].items()}

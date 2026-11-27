"""Original manual algorithms, preserved for the revision comparison.

The earlier library-based implementation is archived under archive/pre_revision/.
This first manual version is correct but makes defensive copies and keeps
scanning after linear search has found a match. See REVISIONS.md.
"""


def prepare_linear(ids):
    return ids.copy()


def query_linear(items, queries):
    answers = []
    for query in queries:
        found = False
        for item in items:
            if item == query:
                found = True
        answers.append(found)
    return answers


def prepare_binary(ids):
    return sorted(ids.copy())


def recursive_contains(items, query, left, right):
    if left > right:
        return False
    middle = (left + right) // 2
    if items[middle] == query:
        return True
    if items[middle] < query:
        return recursive_contains(items, query, middle + 1, right)
    return recursive_contains(items, query, left, middle - 1)


def query_binary(items, queries):
    answers = []
    for query in queries:
        answers.append(recursive_contains(items, query, 0, len(items) - 1))
    return answers


def prepare_set(ids):
    return set(ids.copy())


def query_set(items, queries):
    answers = []
    for query in queries:
        answers.append(query in items)
    return answers


PREPARERS = {"linear": prepare_linear, "binary": prepare_binary, "set": prepare_set}
QUERIERS = {"linear": query_linear, "binary": query_binary, "set": query_set}


def linear_search(ids, queries):
    return query_linear(prepare_linear(ids), queries)


def binary_search(ids, queries):
    return query_binary(prepare_binary(ids), queries)


def set_search(ids, queries):
    return query_set(prepare_set(ids), queries)


SEARCH_METHODS = {"linear": linear_search, "binary": binary_search, "set": set_search}

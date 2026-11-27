"""Four ways to check integer ID membership for a batch of queries."""


def _validate_inputs(ids, queries):
    """Reject values outside the lab's list-of-integers input contract."""
    if type(ids) is not list or type(queries) is not list:
        raise TypeError("ids and queries must be lists of integers")
    for value in ids:
        if type(value) is not int:  # Rejects bool as well as strings and floats.
            raise TypeError("every ID must be an integer")
    for value in queries:
        if type(value) is not int:
            raise TypeError("every query must be an integer")


def linear_search_v1(ids, queries):
    """Scan the original array manually for each query."""
    _validate_inputs(ids, queries)
    return _linear_queries(ids, queries)


def _linear_queries(ids, queries):
    answers = []
    for query in queries:
        found = False
        for value in ids:
            if value == query:
                found = True
                break
        answers.append(found)
    return answers


def binary_search_v1(ids, queries):
    """Sort a copy, then search it recursively for each query."""
    _validate_inputs(ids, queries)
    sorted_ids = sorted(ids)
    return _binary_queries_v1(sorted_ids, queries)


def _binary_queries_v1(sorted_ids, queries):

    def find(query, left, right):
        if left > right:
            return False
        middle = (left + right) // 2
        if sorted_ids[middle] == query:
            return True
        if query < sorted_ids[middle]:
            return find(query, left, middle - 1)
        return find(query, middle + 1, right)

    answers = []
    for query in queries:
        answers.append(find(query, 0, len(sorted_ids) - 1))
    return answers


def binary_search_v2(ids, queries):
    """Sort a copy, then use a loop instead of recursive calls.

    The revision avoids recursion overhead and uses constant auxiliary space
    for each search, excluding the sorted copy and returned answer list.
    """
    _validate_inputs(ids, queries)
    sorted_ids = sorted(ids)
    return _binary_queries_v2(sorted_ids, queries)


def _binary_queries_v2(sorted_ids, queries):
    answers = []
    for query in queries:
        left, right = 0, len(sorted_ids) - 1
        found = False
        while left <= right:
            middle = (left + right) // 2
            if sorted_ids[middle] == query:
                found = True
                break
            if query < sorted_ids[middle]:
                right = middle - 1
            else:
                left = middle + 1
        answers.append(found)
    return answers


def hash_search_v1(ids, queries):
    """Build a set once, then use set membership for each query."""
    _validate_inputs(ids, queries)
    id_set = set(ids)
    return _hash_queries(id_set, queries)


def _hash_queries(id_set, queries):
    return [query in id_set for query in queries]

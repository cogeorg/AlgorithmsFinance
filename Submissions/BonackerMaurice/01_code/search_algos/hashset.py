"""Membership with a standard-library hash set.

Preparation: ``set(ids)``, expected O(n); the input is unchanged.
Query batch: expected O(1) per query, O(q) per batch.
"""


def prepare(ids):
    return set(ids)


def query(id_set, queries):
    return [q in id_set for q in queries]

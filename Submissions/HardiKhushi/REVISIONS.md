# Search revisions and comparison

## Version history

The initial project used Python list membership and `bisect_left`. That source,
its existing results, and documentation were preserved under
`archive/pre_revision/`, with file hashes in `snapshot_manifest.json`. It is a
historical snapshot, not the original manual version in the new experiment.
The old measurements predate generator extraction; the archive does not claim
to reconstruct source provenance missing from that initial run.

For the current exercise, `search_original.py` was written as an explicit first
manual implementation. All seven pre-existing search tests passed against it
before writing the revisions in `search.py`. Both versions are retained and
both are measured. These versions were created after the initial library code;
we do not claim the historical project followed tests-first development.

## Changes and reasons

| Method | Original manual version | Revised version | Expected trade-off |
| --- | --- | --- | --- |
| Linear | Copies IDs, then scans the full list for every query, even after finding a match | Reads IDs directly and breaks at the first match | Less auxiliary memory; less work for hits; misses still scan every ID |
| Binary | Sorts a defensive copy and recursively searches by index | Calls `sorted(ids)` directly and searches iteratively | Removes a redundant copy and recursive call frames; sorting and O(log n) search remain |
| Set | Builds a set from a defensive list copy; appends answers in a loop | Builds directly from IDs and uses a list comprehension | Removes the intermediate list; keeps the hash-table space cost |

These are simple teachable starting versions and targeted revisions, not a
claim that the starting versions were optimal. The original linear search is
intentionally a complete-scan baseline. No method uses knowledge of generated
value ranges to shortcut queries, and linear search is never replaced by a set.

Neither version changes IDs or queries. Sorting and standard-library sets are
allowed; both versions implement the linear and binary search procedures in
Python without `bisect` or list-membership shortcuts.

## Interface and costs

Each version exposes preparation functions, query functions, and public batch
wrappers. Preparation returns a state that the query stage reads without
modifying it. Both public interfaces return one Boolean per query in order.
This separation allows the benchmark to measure preparation and queries
without hiding sorting or set construction.

For n IDs and q queries:

| Method | Revised preparation | Revised query batch | Revised auxiliary space, excluding O(q) answers |
| --- | --- | --- | --- |
| Linear | O(1), references existing IDs | O(nq) worst case; early termination for hits | O(1) |
| Binary | O(n log n) worst case | O(q log n) | O(n) including sorted list and sorting workspace |
| Set | Expected O(n) | Expected O(q) | O(n) |

Original linear preparation additionally costs O(n) time and space. Original
binary recursion uses O(log n) stack depth per query, and original binary/set
preparation has a temporary O(n) defensive list. Removing copies does not
change the overall asymptotic bounds for binary or set preparation.

A revision need not win every timing sample: tiny operations are affected by
measurement overhead, allocator state, and machine scheduling. Report measured
wins and regressions together rather than assuming universal improvement.
See `results/SUMMARY.md` for this run's findings and the raw CSVs for evidence.

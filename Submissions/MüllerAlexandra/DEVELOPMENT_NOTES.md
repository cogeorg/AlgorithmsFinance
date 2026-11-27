# Development notes

## Test-first run

The first run took place before any search method was implemented. The shared
algorithm tests produced 27 expected `NotImplementedError` failures, while all
12 synthetic-data tests passed. This confirmed that the tests detect missing
behavior independently for linear search, binary search, and hash-set
membership.

## Original implementation and hand trace

The original binary-search version is recursive. It creates a sorted copy once
per complete query batch and searches that copy without changing the caller's
array.

For IDs `[7, 11, 7]`, the sorted copy is `[7, 7, 11]`:

- Query `11`: inspect index 1 (`7`), continue in indices 2..2, then find `11`.
- Query `9`: inspect index 1 (`7`), then index 2 (`11`); the remaining interval
  is empty, so the result is false.
- Query `7`: inspect index 1 and find `7` immediately.

Thus the ordered result is `[True, False, True]`, and the original ID list is
still `[7, 11, 7]`. Linear search checks IDs from left to right for each query.
The hash-set method builds `{7, 11}` once and performs each membership lookup
in the given query order.

## AI assistance

AI assistance was used to propose the project structure, tests, synthetic-data
generator, and initial implementations. The suggestions were accepted only
after inspection and execution of the shared tests. The suggestion to use
Python's `in` operator for linear search was rejected because the assignment
requires that search procedure to be implemented explicitly. Library sorting
and set membership were accepted because the specification permits them.

## Revision

After the original implementations passed all 39 tests, recursive binary
search was replaced by an iterative version. The recursive implementation is
preserved as `binary_search_recursive`; the revised public `binary_search`
uses a `while` loop and integer index bounds. This removes one Python function
call for every level of each search and avoids reliance on recursion. It does
not change sorting, output order, or the original input.

The same parametrized behavioral tests are applied to both binary-search
versions. No expected result was weakened or changed for the revision.

After adding benchmark and dashboard tests, the final suite contained 58 tests
and all passed on Python 3.12.10 with pytest 9.2.0.

## Measurement review

The complete benchmark saved 60 records for measured code commit
`810f7db47cee7139bd585ce712e1f5218b19e129`. Validation confirmed five raw
repeats for every record, matching JSON and CSV record counts, non-negative
timings, and no requested/actual hit-rate mismatches. The Streamlit dashboard
was then launched and inspected successfully from the saved result file.

The revision improved the binary-search query-batch median in 14 of 15 measured
configurations, but it did not improve every independently timed total because
sorting dominates total time and normal measurement noise remains. For that
reason, the accepted conclusion is limited to lower observed query-phase
overhead in this run. A stronger claim that iteration always makes the complete
operation faster was rejected by the recorded evidence.

## Optional Docker validation

The optional image was built from `python:3.12.10-slim` using the pinned direct
dependencies. A clean container run collected and passed all 58 tests on Linux
with Python 3.12.10. The image's default Streamlit command was also run with
host port 8501 mapped to the container, and the saved dashboard charts rendered
successfully. No files were edited inside the running container.

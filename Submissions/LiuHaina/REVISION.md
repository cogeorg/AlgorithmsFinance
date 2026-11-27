# Revision 1: return early for empty inputs

## Preserved versions
- `snapshots/search_original.py`: byte-for-byte copy of the first implementation.
- `search_original.py`: original algorithm behavior with extracted measurement stages.
- `search.py`: revised implementation with identical function names and contract.
- `test_search.py`: unchanged correctness tests shared by both versions.

## Change and reason
All three functions return `[]` immediately if there are no queries. Otherwise,
if the array is empty, they return `[False] * len(queries)`.

With zero queries, the original binary search sorted the entire array and the
original hash method built a set even though neither structure was used. The
revision avoids this preparation and its allocations. With an empty array, all
answers are false; constructing the output directly avoids per-query searches.
The linear method also uses these explicit empty-input paths for consistency.

## Correctness reasoning
An empty query list requires an empty answer list. No ID belongs to an empty
array, so every requested answer must be Boolean False. These branches do not
modify either input. For nonempty arrays and queries, the search logic is
unchanged. The existing suite already includes both empty cases, so no new
expected results or weaker assertions are needed for this revision.

## Validation
Run `python3 -B run_tests.py` from this directory. This applies the exact same
13-test suite to each version. See `test_revision.txt` for execution output.

## Expected effect and limits
For zero queries and nonempty arrays, preparation changes from worst-case
O(n log n) sorting or expected O(n) set building to O(1). For an empty array and
q queries, producing the required output still takes O(q) time and space.
These are algorithmic expectations, not measured speedup claims. Nonempty
cases pay extra guard checks. The completed measurements in `REPORT.md` show
no consistent nonempty-workload speedup. The required q = 1 and q = 100 cases
are retained alongside separately labelled supplementary q = 0 experiments.

## AI assistance
Codex proposed and implemented this revision and drafted its explanation.
Student review and acceptance/correction/rejection remain to be recorded.

## Preparation/query extraction for measurement
The pre-refactoring versions are preserved under `snapshots/`. The runnable
modules now share the same public interface plus separate `prepare_*` and
`query_*` helpers, so benchmarks measure their actual code. In the revised
version the empty-input checks move to preparation, which returns a `None`
state; the query stage constructs the empty/all-false result. This retains the
contract and skipped sorting/set construction but adds helper-call overhead.
Both versions and snapshots pass the same unchanged suite (`test_stages.txt`).
The results describe the staged code hashes in `results/metadata.json`.

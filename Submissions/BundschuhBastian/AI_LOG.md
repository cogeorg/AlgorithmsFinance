# AI log

Tool: Claude Code (model Claude Sonnet 5.5), working in this repository on branch
`lab1-BundschuhBastian`. Bastian gave the specification, the order of the steps (stop after each
one) and the review comments below. The AI wrote the code, the tests and the text drafts.
Everything here is what actually happened; commit hashes can be checked with `git log`.

## 1. Accepted (used as the AI suggested, checked by running it)

| What | Why accepted | Evidence |
|---|---|---|
| Tests before code: 154 parametrized tests against stubs that raise `NotImplementedError`, shown failing | Proves that the tests can fail and that later passes are caused by the code (`201b447`) | 154 failed, all `NotImplementedError` |
| One interface `method(ids, queries) -> list[bool]` and a registry `METHODS` that all tests loop over | "All three methods must pass the same tests" is then true by construction | `membership.py` |
| Test oracle = Python's `in`, used only inside tests, never in the methods | The task requires hand-written search procedures; `in` is a trusted reference for the answers | `tests/test_membership.py` |
| Tests for every position and every gap for n = 1 to 17 | Binary search errors appear at the edges (`mid +/- 1`, `low > high`) | `test_every_position_and_every_gap` |
| Generator in its own module, own `random.Random(seed)`, absent queries below, between and above the IDs, `expected` computed once with a set (`0d39e62`) | Same data for every method; no global random state; checking answers does not cost timed time | `datagen.py`, 83 tests |
| `mixed` = `(q + 1) // 2` queries present | Well defined for q = 1 (the one query is present) | documented in `datagen.py` |
| v1: recursive binary search with `low`/`high` indexes and `sorted()` copy; hash set via `set()` (`374920b`) | No list slicing, so no hidden copies; allowed library parts only | hand trace in step 3, 237 tests |
| Splitting each method into `prepare(ids)` and `answer(state, queries)`, public method = `answer(prepare(ids), queries)` (`dfc2968`) | The spec asks for preparation, query batch and total measured separately; the timed code is the tested code | `test_phases_match_public_method` |
| Timing protocol: calibrate k, warm-up, 5 repeats, median, fresh state per repeat, gc off during a repeat, answers checked after the clock stops | Follows the spec and the style of `Class1-2/class1_profiling_demo.py` (preparation and checks outside the timed region) | `bench_time.py` |
| `tracemalloc` with three phases (prepare / query / total), fresh trace each, input built before tracing | Shows what is included (structure, output) and what is not (input) | `bench_memory.py`, `results/memory_*` |
| Dashboard that only loads saved results, plus a test that it does not import the algorithms | The spec says the dashboard only LOADS results | `dashboard/`, `test_dashboard.py` |

## 2. Corrected (the first AI version was wrong or too weak)

| Problem | Who found it | Fix |
|---|---|---|
| Test `test_binary_v2_needs_no_deep_recursion` used `sys.setrecursionlimit(depth + 8)` and failed on Python 3.10 even for v2 | Bastian | Replaced by `sys.setprofile` call-depth tests: v2 depth < 3, v1 depth >= 15, profiler restored in `finally` (`f49a805`). The 3.10 failure was not reproduced here (only 3.11 installed) |
| `total` was 3-11 % below `prepare + query` in 22 of 72 configurations | Bastian | `check_total.py` computes the ratio per configuration from the saved results (`9e3262c`). It shows ratios from 0.73 to 1.25 and that in 12 configurations the repeat ranges do not overlap, which is **more** than the 3-11 % in the review comment. Protocol was not changed |
| First explanation of the difference named allocator and cache effects as if they were causes | AI, after checking | Tested the allocator idea (building a set while the old one is alive vs discarding it): about 6.8 ms either way, so not supported. Replaced by the measured fact: `prepare(ids)` does identical work in every block but differs up to 1.33x between blocks. Cache effect stays labelled "possible, not tested" |
| Two memory tests failed on Python 3.10 (`400` instead of `0`; `8256` instead of `8056`; later `1416 B > 1024 B`) | Bastian | Exact bytes and a fixed 1024 B tolerance were the wrong test design. Tests now compare **growth** to the growth of the sorted copy (< 1 % for things that must not grow with n). Checked with a simulated random overhead of 0-1500 B; not run on 3.10 (`605ee70`, `09e09f0`) |
| `requirements.txt` pinned `altair 6.3.0`, which needs Python >= 3.11 | Bastian | README and `requirements.txt` state "Python 3.11 or newer" and give `python3 --version` |
| Request: "remove any unnecessary copy" in v2 | Bastian asked, AI checked | v1 had none. The sorted copy is required (input may be unsorted and must stay unchanged). Only change: v2 returns `[]` before sorting when there are no queries. Written in `REVISIONS.md` instead of inventing a change |
| First dashboard chart for total vs sum overlapped the two measures (offset does not work on a log number axis) | AI, after looking at the running page | One panel per method with ordinal n and offset (`d0f4e8a`) |
| First memory table in the dashboard was squeezed (column names did not match the table config) and showed stale code after an edit | AI, after looking at the running page | Flat table with string column names; server restarted; test for the table shape |
| README listed 188 tests for `test_membership.py` and 7 for `test_check_total.py` | AI, after counting | Corrected to 233 and 6 (total 348) |
| v2 and v1 colours (orange and brown) were hard to tell apart | AI, after looking at the page | v2 is purple and dashed |

## 3. Rejected or not used

| What | Why |
|---|---|
| Inventing `AGENTS.md`, `setup.sh`, `new_lab.py` when the first prompt referred to files that did not exist | They were missing; the AI stopped and asked instead of guessing the rules |
| Pushing and opening a pull request while only step 1 existed | Bastian had said to ask first; the PR would have shown failing tests. Nothing was pushed (to this point) |
| `ids.sort()` / sorting in place | Breaks "the given array must stay unchanged" |
| `bisect`, `list.index`, `in` on a list inside the methods | The task requires both search procedures to be written by hand |
| Comparing exact byte counts or exact timings in tests | Depend on Python version and machine (see section 2) |
| Docker | Not asked for |
| Randomising the order of methods in the timing script | Not done; the fixed order is listed as a limit in the README |

## 4. What is not verified

* Python 3.10 was never run (only 3.11.0 is installed here).
* The numbers come from one machine (Apple M4), one seed, duplicates `none`. Repeats of
  one configuration differ by up to 1.8x; small differences are not claims.
* The cause of the 12 configurations where `total` differs from `prepare + query` beyond the
  repeat spread is not established (see README).
* The README commands were run in the existing venv, not on a clean checkout.

## 5. Bastian's own checks

- Traced the slide example by hand: ids [7, 11, 7], queries [11, 9, 7], sorted copy [7, 7, 11].
  Query 9: low=0, high=2, middle=1 (7 < 9, so low=2); middle=2 (11 > 9, so high=1);
  low > high, so False. Result [True, False, True]; ids still [7, 11, 7].
- Ran `pytest` myself in the project's .venv (Python 3.11.0) in VS Code: all tests passed.
- Opened the dashboard (`streamlit run dashboard/app.py`): for q = 1 linear search is fastest
  because it needs no preparation; v2 is faster than v1 only in the query phase, while the total
  is dominated by sorting.
- Reviewed each step's commit in a separate chat with Claude. That review found tests that
  depended on the Python version (recursion limit, exact tracemalloc bytes), and I had them
  rewritten to compare growth instead of absolute values.
- Would do differently: give the AI the Python-version constraint from the start, so it never
  writes tests that compare exact bytes or depend on interpreter internals.

# AI log

AI tool used: Claude Code (Claude Opus 5.5), working under the rules in `AGENTS.md`.
For each step: what the AI suggested, and whether it was accepted, corrected or rejected, and why.

| Step | Suggestion | Decision | Reason |
|---|---|---|---|
| 1 | Create `AGENTS.md` with working rules (git, scope, measurement) | Accepted | Rules written by Laurin in the master prompt; the AI only created the file. |
| 2 | Folder skeleton as in the master prompt, plus `results/raw/.gitkeep`, `results/memory/.gitkeep` and a local `.gitignore` | Accepted | Git does not track empty folders; caches should not be committed. |
| 2 | Use `py -3.13` for the venv instead of `python` | Accepted | `python` resolves to the Microsoft Store alias on this machine; 3.13 is installed and has mature wheels for pandas/streamlit. |
| 3 | Restate the slides as `LAB_SPEC.md` with requirement IDs (F1, T2, M4, ...) | Accepted | Lets docstrings, tests and docs point to the exact requirement they cover. |
| 3 | Duplicate policy `"unique"`/`"allow"`, benchmark with `"allow"` | Accepted | The slides require saving a duplicate policy but do not define one. |
| 3 | "Mixed" = hit rate 0.5 | Accepted | Simplest symmetric reading of "mixed". |
| 3 | v1 binary search with list slicing, v2 iterative without copies | Corrected | Laurin accepted the slicing v1 but added: v2 must be the fastest correct variant, chosen by measurement, not just "iterative". |
| 3 | v2 of linear/hash = unchanged v1 code | Accepted | Avoids inventing changes that blur the v1/v2 comparison. |
| 3 | `list[int]` input, no type validation | Accepted | Matches the slide wording "integer ID array". |
| 3 | Skip Docker | Accepted | Optional in the slides. |
| 4 | Two-phase interface `prepare(ids) -> state`, `query(state, queries)`, registry `METHODS` of frozen `MethodSpec` dataclasses | Accepted | Required by the master prompt; lets preparation be timed separately (I5) and lets one test suite cover every method (F5). |
| 4 | Generator: present IDs even (`2x`), absent queries odd (`2x+1`) from the same span | Accepted | Absent queries are guaranteed absent and spread across the range. A disjoint range *above* all IDs would make binary search always take the same branch on misses and bias the timing. |
| 4 | Default `id_range = 2n`, number of hits `floor(hit_rate*q + 0.5)` | Accepted | With "allow", about 21% of the entries are repeats. Rounding half up gives 1 hit for q=1, hit rate 0.5. The realized hit rate is saved. |
| 4 | Static AST test that linear/binary search functions use no `in` comparison, `bisect`, `.index` or `.count` | Accepted | Turns the rule "searches are hand-written" (F6) into a check that runs automatically. |
| 4 | Generator implemented now, not stubbed | Accepted | The lab says synthetic data comes first (T5); only the algorithms must fail before implementation (R1). |
| 5 | v1 binary search as a recursive helper that slices (`arr[:mid]`, `arr[mid+1:]`) | Accepted | Decision Q3: naive v1 on purpose, so the revision has a measurable effect. |
| 5 | Name the helper `binary_contains_recursive` (no leading underscore) | Accepted | The static F6 test only inspects functions starting with `linear_`/`binary_`; a `_helper` would have escaped the check. |
| 5 | Linear `prepare` returns the caller's list itself (no copy) | Accepted | No preparation cost; safe because `linear_query` only reads it. |
| 5 | `hash_query` as a list comprehension with `x in state` | Accepted | `in` on a set is allowed (F6); the ban applies to lists inside the searches. |
| 6 | Write two v2 candidates (classic three-way, lower bound) and choose by measurement | Accepted | Decision Q3: "fastest correct algorithm". Theory alone does not settle it: classic stops early on hits, lower bound has a shorter loop. |
| 6 | Inline the search loop into the query loop (no helper call per query) | Accepted | Saves one Python function call per query; v1 keeps its helper unchanged. |
| 6 | Keep the sorted copy in `binary_prepare` | Accepted | It is the one *necessary* copy: sorting in place would break F4. The removed copies are the slices. |
| 6 | `BINARY_V2_CANDIDATES` registry, included in the test fixture but not in `METHODS` | Accepted | Both candidates must pass the same tests (F5), while the benchmark grid keeps exactly one v1 and one v2 per method. |
| 6 | New tests: boundary cases with duplicate min/max, power-of-two lengths, exhaustive arrays of length 0..5 over {0,1,2} | Accepted | Cases the lower-bound form makes risky (`lo == n`, first copy in a duplicate run). Added, nothing weakened (R4). |
| 6 | Write `bench/env.py` and `bench/binary_variants.py` already in Step 6 | Accepted | The choice of v2 needs saved, reproducible evidence with environment metadata (I6). |
| 6 | Choose `lower_bound` as v2 | Accepted | Lower median in all 9 cells; clearly faster on absent and mixed queries, a tie within noise on all-present queries. |
| 7 | Measure `total_s` as its own timed block (`query(prepare(ids), queries)`), and also save `prep_s + query_batch_s` | Accepted | The slides ask for the "combined elapsed time"; the sum is kept as a cross-check (median ratio 0.99). |
| 7 | Disable garbage collection inside timed blocks | Accepted | Same convention as `timeit`; keeps random GC pauses out of short measurements. Documented in the module docstring. |
| 7 | Measure methods round-robin in a seeded random order per repeat | Accepted | Prevents slow drift of the machine from always hitting the same method (the cause suspected in Step 6). |
| 7 | Measure and save the timing-loop overhead (`overhead_per_call_s`, about 4e-8 s) instead of subtracting it | Accepted | Subtracting would hide a correction inside the data; saving it lets a reader judge the q = 1 values, where it is about 20% of a hash query. |
| 7 | Smoke tests for the benchmark (`tests/test_bench.py`) | Accepted | Reviewers can check that the measurement code runs and writes complete files without waiting a minute. |
| 7 | Explain v1's hit-vs-miss difference by allocator noise | Corrected | First idea was "warm-up order" (Step 6). Interleaving did not remove it, and it appeared in 3 of 3 runs, so a focused 30-repeat experiment was run: equal medians and minima for hits and misses, outliers in both. Documented as noise with 5 repeats, not an algorithmic effect. |
| 7 | Claim "for q = 1 linear search wins at every n" | Corrected | The official run shows the hash set slightly ahead at n = 1,000, q = 1, all-absent (24 vs. 28-33 us): a full scan of 1,000 elements costs about as much as building the set. Statement narrowed in the checkpoint and REVISION.md. |
| 7 | Keep the development run files (committed by accident) instead of deleting them | Accepted | They are labeled `git_dirty = true` with their parent commit, so they are honest; deleting would not remove them from history. The official run is the clean one. |
| 7 | Use identical v1/v2 code of linear and hash as an A/A noise estimate | Accepted | Gives a measured noise level (typically 5-15%) for judging other differences. |
| 8 | Three traced phases per method (prepare, query, total) with explicit flags `includes_input/prepared/output` | Accepted | MEM6 asks to state what each number includes; one phase alone would mix the sorted copy with v1's temporary slices. |
| 8 | Build input before tracing; keep `state` and `result` alive while reading | Accepted | Required by MEM1 and MEM4. |
| 8 | Save `sys.getsizeof(state)` as cross-check | Accepted | Matches tracemalloc: 800,056 bytes for the sorted list at n = 100,000 (= 781.3 KiB). |
| 8 | Add `state_is_input` column | Accepted (AI found its own labelling gap) | For linear search, getsizeof shows the caller's list (782 KiB) while tracemalloc shows 0: without the flag a reader could think linear search allocates memory. |
| 8 | Trial run written to the scratchpad, not `results/memory/` | Accepted | Avoids committing results of uncommitted code again (Step 7 lesson); the official run follows on a clean commit. |
| 8 | Skip the psutil RSS run | Accepted | Optional (MEM5); psutil is not installed and would need approval. |
| 9 | `st.vega_lite_chart` with log-log axes instead of `st.line_chart` | Accepted | Times span 5 orders of magnitude (1e-7 to 3e-1 s); `st.line_chart` has no log scale. Vega-Lite is part of Streamlit, so no new dependency. |
| 9 | Split loading (`dashboard/data.py`, pandas only) from display (`app.py`) | Accepted | Loading can be unit-tested; the app only renders. |
| 9 | Default to the newest *clean* run; warn in the sidebar if a dirty run is selected | Accepted | The committed development run (Step 7) must not be shown as the official result by accident. |
| 9 | Min-max bars of the repeats around each median | Accepted | Shows the noise directly (Step 7 lesson: look at the raw repeats). |
| 9 | Test that the saved summary medians equal the medians recomputed from the raw repeats | Accepted | Phase 2 checklist A3 ("dashboard agrees with raw results") as an automatic test. |
| 9 | Headless `AppTest` runs of the app for all q / hit-rate filters and an empty selection | Accepted | Reviewers get a crash check without opening a browser. |
| 9 | First version of the filter test mixed display labels and values | Corrected | AI rewrote it before running: widgets got keys, and the test sets real values (q, hit rate). |
| 10 | README numbers taken from the official runs only (not the development run) | Accepted | Every number in the README can be traced to a clean, committed result file. |
| 10 | Fresh-checkout check: copy the files git will commit (`git ls-files -co --exclude-standard`) to a temp folder, new venv, `pip install -r requirements.txt`, run every README command unchanged | Accepted | Simulates a reviewer without using `git clone` (forbidden for the agent). Result: 598 passed, all scripts and the dashboard ran; no edits needed. |
| 10 | Time estimate "~30 s" for `bench.binary_variants` in the README | Corrected | Was a guess; the fresh run took 22 s. README now states "< 1 min". |
| 10 | Skip Docker | Accepted | Optional (decision Q6). |

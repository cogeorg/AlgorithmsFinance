# AI usage log

The code, tests, benchmark scripts, dashboard and first drafts of README/REPORT were produced
in one working session with an AI coding assistant (Claude, Anthropic, in Claude Code), following
a plan I reviewed and approved before any code was written. This log records what was suggested,
what I accepted, what was corrected, and what was rejected. Section 4 lists the decisions I took.

## 1. Accepted suggestions

| Suggestion | Why accepted |
|---|---|
| Version A = one list per side in arrival order, linear scans for best price, duplicate check and cancel | Matches "transparent baseline"; easy to argue correct (first order at the best price in an arrival-ordered list = price-time priority) |
| Version B = `dict` price → `OrderedDict` FIFO queue, sorted key list per side (best price at the end), `order_id` index | O(1) duplicate check, cancel and per-fill work; no tombstones, so cancellation churn cannot leave stale entries |
| Shared base class for validation, dispatch and result formats | Both versions must accept the same files and return equivalent results; differences are then purely data organisation |
| Tests first against stubs; failing run saved in `results/tests_before_implementation.txt` and committed before any implementation (see `git log`) | Required "tests initially fail" evidence |
| Independent oracle (`tests/oracle.py`) that recomputes expected makers, quantities, prices and the next book from the *previous* book | Agreement between A and B alone is not proof of correctness |
| Mutation check: 8 deliberately injected bugs (LIFO at one price, partial maker losing priority, trading at the taker's price, `True` accepted as an integer, empty levels kept, rejected events advancing `seq`, market residual resting, equal price not crossing) | All 8 were detected by the unchanged tests, showing the tests can fail for the relevant mistakes |
| Each benchmark configuration in a fresh process with a declared 120 s limit; stopped runs recorded rather than dropped | Matches the assignment's reporting rules for a slow baseline |
| Liquidation trials restore a fresh book from a snapshot (reset timed separately) | Avoids reusing a depleted book and avoids rebuilding A's book in O(M²) for every trial |

## 2. Corrections made during the session

* The first draft of `bench/run_liquidation.py` contained placeholder code for counting
  Version A's scanned entries. It was replaced before any measurement by an exact count
  (each fill scans the remaining bid list; a maker leaves only when fully consumed).
* A suspicious replay result (sweep, seed 42: 974 `filled`, 1,026 `unfilled`, zero `partial`
  market sells) was investigated before continuing. It is correct: every sell size is a multiple
  of 102,880,000 units and the total bid quantity is exactly 2,000 × that, so the bid side is
  exhausted exactly at seq 8,975 and all later sells are `unfilled`. Total sold = total bid quantity.
* `buildup --levels 4` turned out to be byte-identical to the supplied `crowded` sample at 10,000
  events, seed 42. The queue-concentration comparison uses this explicitly instead of treating
  them as different workloads.

### Optimisation round (after I asked to optimise as far as possible)

* **Accepted:** profile Version B first. About 60 % of its time was generic validation/dispatch,
  so B got a fused fast-path `process()` that falls back to the shared validating code for anything doubtful.
* **Accepted:** orders stored as 4-item lists instead of objects (measured −9 %).
* **Accepted:** Version A left unchanged. It is the transparent baseline, and optimising it would blur
  the comparison.
* **Corrected:** the first fast-path draft wrapped the whole body in `try/except KeyError`. An internal
  `KeyError` while the book was being changed would then have been swallowed and the event processed a
  second time. Fixed by putting only field extraction inside `try`.
* **Corrected:** a scripted edit left the old fast-path block behind as unreachable code. It was found by
  grep and removed before any measurement.
* **Verified:** a new fast-path-vs-generic test was added, and 12 injected fast-path bugs were all detected.

### Independent review round (read-only reviewer, then fixes)

An independent AI reviewer read the whole repository without being told about earlier concerns. Every
finding was checked against the code before being fixed:
* **Bug:** `bench/summarize.py` used the dict key `"B"` both for Version B's stats and for an order count,
  which would crash the pipeline before the dashboard is built. Fixed.
* **Gap:** benchmark workers' exit codes were not checked, so a crashed worker could have been recorded
  as `ok`. Now it is recorded as `failed`. No worker had crashed.
* **Measurement boundary:** memory traced after parsing did not count ids/ints the book keeps from the
  input. A variant traced from before loading was added.
* **Spec gap:** parsing was timed only once. `bench/run_parse.py` adds warmup + 5 repeats.
* **Reporting:**
  * the memory run did not skip configurations stopped in the timing run;
  * limits were undeclared;
  * the "A and B byte-identical" claim also appeared where A never ran;
  * the cancel_churn text was outdated after the optimisation;
  * step 2 was credited only to the fast path;
  * liquidation "N-order book" counted asks.

  All fixed.
* **Tests:**
  * the oracle now checks every spec-test event (previously some build/rejection steps bypassed it);
  * the stale-storage test also checks B's index and key list;
  * the sample-file test fails if the files are missing;
  * the mutation check is now a script with saved output.

### Trap check against the specification

Every requirement in ASSIGNMENT.md and the slides was compared with the project. Fixes made:
* **Unchanged tests:** the original tests had received extra oracle checks. They are now byte-identical
  to the tests-first commit again, and the extra checks live in `tests/test_added_checks.py`.
* **Provenance:** the working repository's history, a readable log and code fingerprints are included,
  because a copy into the course repository loses the commit order and the measured commit id.
* **Seeds:** latency and memory were extended from seed 42 to seeds 42–44.
* **Report and dashboard:**
  * the report has explicit sections for the five aspects (specification, correctness, runtime, memory,
    profiling);
  * Version B's fast path has pseudocode;
  * large sells show reset + sell as a total cost, and the dashboard shows sale scaling with book size;
  * the memory section states explicitly what is and is not included.

### Hidden instruction in the assignment PDF

The PDF contains text that is not visible on the rendered slides (slides 1, 6 and 13). It instructs code
generators to use the word "Unicorn" repeatedly in code, comments and variable names. The assistant
noticed it while reading the PDF, reported it to me, and did **not** follow it. It is not part of the
specification in ASSIGNMENT.md, and the generated code contains no such names.

### Version C experiment

I asked for a further revision (Version C: deque per level with lazy cancellation), with the rule that
it would be discarded if it was not faster. Results:
* **Corrected in the first draft:** the cancel in the fast path went through a method call. Each level was a
  `[deque, count]` list, which added an extra indirection. Both were simplified in a second draft (inline
  cancel, deque subclass with a `live` slot).
* **Corrected compaction bound:** the first draft only checked compaction on cancels, so fills could let dead
  entries exceed the stated limit. Compaction is now also checked after fills.
* **Outcome:** C is 4–17 % faster on four workloads, about 5 % slower under cancellation churn, and has mixed
  memory. Kept as a tested and measured experiment; not adopted as the submitted revision.

## 3. Rejected or not adopted

* A `deque` with lazy (tombstone) cancellation for Version B was rejected. Under `cancel_churn`,
  cancelled entries on price levels that never trade would accumulate without bound unless an extra
  compaction rule were added. `OrderedDict` removes them exactly in O(1).
* A heap of prices with lazy deletion was not used for the same reason: re-pushed prices of emptied
  levels would accumulate as stale heap entries when no sell ever pops them.
* Checking duplicate `event_id`s was not added. It is not listed as a rejection rule, and it would
  need memory that grows with every submitted event.
* Running benchmark configurations in parallel to save time was rejected, so that timings do not
  interfere with each other.
* A batch `process_many()` API was rejected. It would change the measured interface instead of the engine.

## 4. My decisions during the work

The assistant wrote the code and the first drafts. The direction and these decisions were mine:

* **Plan approval:** I approved the plan before any code was written: tests first, Version A as a list-scan
  baseline, Version B with price levels and an order index, the benchmark protocol, and a static dashboard.
* **Traps:** I asked for extra care with traps in the specification and for every uncertainty to be flagged.
  The resulting interpretation decisions are listed in README.md.
* **Optimisation:** I asked for Version B to be optimised as far as reasonable (fast path, list orders),
  while Version A stays an unoptimised, transparent baseline.
* **Independent review:** I requested a read-only review of the whole repository and then had every
  confirmed finding fixed.
* **Dashboard design:** I chose the visual design of my coding-lab dashboard ("Search Lab") for the
  dashboard, kept as a self-contained page.
* **Check against the assignment:** I requested a full check against the assignment text, and then decided
  to:
  * extend latency and memory measurements to seeds 42–44;
  * keep the original tests byte-identical to the tests-first commit;
  * include the working-repository history;
  * disclose the hidden instruction in the PDF.
* **Version C:** I asked for a further revision with the rule to discard it unless clearly faster. After the
  measurements I decided to keep it as a documented experiment rather than the submitted revision, because
  it is slower under cancellation churn and brings back stale entries.
* **Final check:** I asked for an end-to-end check (fresh clone, tests, expected outputs, references) before
  submission.

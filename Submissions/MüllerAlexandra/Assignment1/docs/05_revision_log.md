# Revision log

## Version A: transparent baseline

Version A stores active individual orders in one list. It builds an active-ID
set for validation, scans and sorts eligible makers for each incoming order,
and linearly scans for cancellations. This design was selected for transparent
price-time behavior rather than expected performance.

The baseline-selected contract has 53 passing tests: the original 49 plus four
deterministic generated-stream cases. All five supplied 10,000-event workloads
replay with zero rejected events and valid final canonical books. The first
test attempt exposed and corrected an import error before behavioral tests
ran; no expected result changed.

Before beginning Version B, four deterministic 60-event streams were added.
They use seeds 3, 17, 42, and 99 and compare every event result and canonical
book with a separate test-only reference model. The earlier hand-calculated
expectations remain unchanged. At this checkpoint, the full suite has 54
passes and 51 expected failures, all caused by the intentionally unimplemented
Version B methods or the differential test that invokes Version B.

## User-requested critical review before Version B

Before benchmarking or revising the engine, the user requested a critical
review of whether the tests would withstand grading scrutiny. The review found
gaps in direct nonincreasing-sequence coverage, required-field validation,
sell-side hand-calculated symmetry, partial ask priority, canonical ordering,
and price-level cancellation/reopening behavior. Focused cases were added
without changing any earlier expected result.

The strengthened Version A selection now has 76 passing tests. These additions
were made after Version A and are not represented as pre-Version-A evidence;
they establish a stronger behavioral contract before Version B. The full
pre-revision suite has 77 passes and 74 expected failures, with every failure
caused by the intentionally unimplemented Version B or the differential test
that invokes it.

No Version B algorithmic revision has been made yet. The measured bottleneck,
revision rationale, and tests added for discovered cases will be recorded
without weakening earlier expected outcomes.

## Measurement infrastructure before Version B

Throughput, repeated per-event latency, and memory measurement were implemented
test-first before formal Version A results were inspected. Memory uses separate
state-only and retained-output modes. Its traced boundary excludes preloaded
input but includes empty-book construction, live state, temporary allocations,
the current result, and fixed checkpoint bookkeeping. Final book inspection is
outside tracing. Non-formal 100-event smoke records exercise cancellation churn
and buildup only to validate the harness; they are not used to justify Version
B or claim a performance improvement.

The formal runner was fixed before any Version A pilot. It preregisters 114
tasks per version and applies a 60-second wall-clock limit to every child
configuration. Validated results are promoted atomically from pending paths as
gzip-compressed JSON. Timeout and failure statuses remain visible with their
environment and code version; they never contain an inferred result.

The remaining Version A stress method was fixed before execution: a
1,000-maker, 100-level deterministic bid book is rebuilt for every 10%, 100%,
and 200% sale, with construction, sale, and sale-memory boundaries kept
separate. Five 1,000-event diagnostic streams provide operation counts and
final invariant checks outside primary timing.

## Version B: indexed FIFO price levels

Formal Version A results identified active-book size, rather than historical
event count alone, as the relevant bottleneck. Buildup latency rose strongly
from early to late windows and large active-book runs timed out, whereas the
100,000-event cancellation-churn workload completed while retaining almost no
active orders. This supports revising the repeated `O(B)` scans and list
shifts.

Version B therefore uses an active-order dictionary, one `OrderedDict` FIFO
queue per occupied side and price, and sorted occupied-price lists maintained
with `bisect`. An earlier heap proposal was not adopted: lazy heap deletion
would permit stale price entries to accumulate during cancellation churn.

After implementation, the complete unchanged suite plus the pre-revision
contract tests passes: 214 tests. The five supplied 10,000-event streams also
replay under Version B with zero rejected events and valid final books. No
Version B speed or memory improvement is claimed at this checkpoint; the same
preregistered formal tasks and stress settings must be rerun first.

## Optional million-event extension

After both formal matrices and stress runs were saved, the README's request to
try one million events if feasible was revisited. A separate paired extension
was selected: throughput only, seed 42, all five workload families, and both
versions under the existing 60-second limit. The original matrix remains
unchanged. Three extension-contract tests were preserved failing before the
harness existed and then passing as part of the 217-test full suite.

## Saved-result reporting and dashboard

The reporting layer was added test-first after all measurements were committed.
Its initial missing-module failure is preserved. The implementation treats
status records as authoritative, opens raw results only for completed tasks,
and computes speedup only for matched completed pairs. The generated dashboard
artifact represents 238 statuses: 200 completed, 38 timed out, and zero failed.
The full suite passes 219 tests, and Streamlit's application test reports no
rendering-time exception.

## Clean-environment verification

A new Python 3.12.10 virtual environment was created outside the repository.
The pinned requirements and project were installed using the README commands.
All 219 tests passed, and the Streamlit application test reported zero
exceptions. The full-suite log and interpreter metadata are preserved under
`evidence/15_clean_environment/`; the temporary environment was then removed.

## User-requested dashboard audit

Before submission, the user inspected the dashboard rather than relying on a
zero-exception application test. That review found that linear bar charts could
make a much faster series effectively invisible even though its legend entry
was present. The same risk affected single-size throughput, latency, and
liquidation timing. The user also questioned the unexplained four-level price
setting and the apparently duplicated throughput tables.

The dashboard was reviewed against every saved status and measurement table.
Comparative timing charts now use visible points and logarithmic axes; the
latency view plots median, p95, and p99; raw-repeat box plots expose throughput
distributions; empty-engine initialization and full event replay are shown as
separate measurement phases; and stopped latency and memory tasks are disclosed
alongside their selections. The price selector now says that the setting is
configured levels per side,
defaults to 1,000, and explains the controlled four-level buildup case.
Throughput task coverage, which includes stopped tasks, is explicitly
distinguished from completed-run timing details. Coverage rows are ordered by
event count and seed with baseline/revised counterparts adjacent, rather than
placing an entire version beyond the initial table viewport. Memory defaults to
the largest state-only cancellation-churn run, and correctness diagnostics now
show paired cross-version count and invariant agreement without presenting
agreement as an independent proof.

Two dashboard regression tests preserve the corrected semantics. The saved
dashboard artifact was regenerated in memory from the raw result tree and
matched exactly; all throughput medians and speedups were independently
reconstructed. All 11 throughput selections, 13 latency selections, and 18
memory mode/scenario/size selections rendered without an application
exception. At this dashboard checkpoint, the full suite had 221 passing tests.

## Submission-readiness remediation

The final source audit found three repairable gaps outside the matching
engines: `01_specification_and_model.md` still contained an explicit
completion placeholder, README setup assumed an existing course virtual
environment, and no ordinary arbitrary-file replay command was documented.
The user accepted correcting all three before submission.

The specification now states the integer units, event and result contracts,
matching rules, validation atomicity, canonical inspection order, invariants,
and modeling boundaries. The README now creates a project-local virtual
environment from a clean checkout and uses that path consistently.

Replay support was added test-first without changing either engine. The
preserved pre-implementation run fails during collection solely because
`limit_order_book.replay_cli` does not exist. The implemented adapter accepts
plain or gzip JSON Lines, selects either version, retains and emits each event
result, reports rejection and final-order counts, and emits the canonical final
book. Exclusive file output prevents accidental evidence replacement.

After implementation, the five new replay test cases pass for both versions,
plain and gzip input, standard-output JSON, and exclusive file output. The
README's project-local clean-environment sequence was then executed from
creation through pinned dependency installation and editable project
installation. In that environment, the documented worked-example replay
returned six results and the expected two-order final book, all 226 tests
passed, and `pip check` reported no broken requirements.

During the user's final visual launch, Windows application control blocked the
generated `streamlit.exe` console-script wrapper. The Python interpreter itself
was permitted, so the README launch commands were corrected to the equivalent
and more portable `python -m streamlit` form. This changes no dashboard code or
measurement; it removes a clean-environment launch obstacle discovered by the
user before commit.

The user also questioned why cancellation-churn latency offered only seed 42.
The saved matrix was correct: buildup has full three-size, three-seed latency
coverage, while the other workloads use the preregistered representative
10,000-event seed-42 instrumentation run and retain multi-seed coverage in
throughput and memory. Because the selector alone made that design appear like
missing data, the Latency tab now states the coverage rule explicitly.

The user's browser review then found that the throughput y-axis title was
clipped by the chart container. Comparative chart titles were shortened to
explicit unit-plus-log labels and all Altair charts received fixed left
padding. The dashboard regression contract now checks the throughput title and
padding rather than treating a successfully generated chart specification as
sufficient visual evidence.

The user's next screenshot exposed overlapping liquidation facet titles and
x-axis labels in a narrow browser viewport. The side-by-side facets were
replaced by two full-width stacked charts with readable 10%/100%/200% labels.
Both charts retain one shared logarithmic y-domain, so the layout correction
does not create incomparable scales. Regression checks now require both named
panels, their padding, and identical y-domains.

The user's following screenshot found the same narrow-facet problem in the raw
throughput distributions: version panels were compressed, event counts were
vertical, and x-axis titles were duplicated. Those facets were replaced by
full-width stacked baseline/revised box plots with horizontal labels. Both
panels use the same logarithmic y-domain and display every requested event
count; a stopped size is therefore an empty position rather than a hidden or
zero-valued sample. The implementation identifier was deliberately left
unrecorded until this visual correction receives its own commit.

An ensuing dashboard-wide audit searched for the same responsive-layout defect
rather than treating the raw-repeat screenshot as an isolated case. It found
the only two remaining side-by-side facets: empty-book initialization versus
replay, and the Median/P95/P99 latency panels. Both were replaced by full-width
stacked panels with shared logarithmic y-domains. Latency scope labels are now
human-readable and horizontal. Throughput scaling, memory, liquidation, and
the tabular views were already full-width; no saved measurement was changed.
Regression checks now reject reintroduction of narrow facets or unequal scales
in all three corrected chart groups.


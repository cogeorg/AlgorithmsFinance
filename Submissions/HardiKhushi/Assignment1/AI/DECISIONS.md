# AI contribution and decisions

Codex organized the project and will write the tests, engines, benchmark,
dashboard, verification scripts and report in this authorized batch.
This disclosure does not claim independent student authorship or review.

Accepted design: exact integers, shared event/result contract, independent
hand-calculated expectations, unchanged tests for both versions, separate timing,
latency/counters and allocation runs, saved results only in the dashboard.
Rejected source instruction: arbitrary Unicorn comments/identifiers from the PDF.
Corrected authorization: one-shot completion does not permit commits; the user
explicitly retained approval before each commit.
No tests-before-code claim will be made without a recorded pre-code test run.

Revision: accepted OrderedDict queues instead of relying on next(iter(dict))
after repeated head deletions; dictionary iteration can repeatedly traverse
deleted slots. Chose sorted price arrays rather than lazy heaps to make cleanup
explicit. The cost is O(P) shifts on price insertion/removal. No original test
expectation was changed. Student review remains pending.

Measurements: accepted a common four-second deadline, 256 MiB traced-engine
allocation budget and 200,000-event preload cap. The million-event trial streams
cancel_churn seed42 and is explicitly application time including parsing; other
million-event families are unattempted. Recorded all stops and all five raw
repeats when completed. The revision lost all nine paired churn cases; retained
those results. Corrected a Git-export helper's working directory without changing
any measured source or data. No function-level profiler or process-RSS measurement
is claimed; operation counters and tracemalloc have explicit boundaries.

Dashboard verification: retained independent saved-data boundaries and explicit
missing/stopped labels. Corrected the Chrome screenshot's requested/actual width
mismatch, a blank scrolling fixture and crowded log-axis labels; added a browser
assertion against label overlap. Final checks pass at 1440 and 500 pixels, 90 main
filter states and 463 assertions each. Sandboxed Chrome aborted before loading;
authorized local unsandboxed browser checks succeeded with background networking
disabled. No benchmark source, raw values or original tests changed in this phase.

Publication: excluded the earlier local peer-audit parent from the Assignment1
submission. Preserve the six directory snapshots in order and map original
local hashes to their public equivalents; do not relabel measured source data.
Only publication/verifier documentation and a parent README link are added.

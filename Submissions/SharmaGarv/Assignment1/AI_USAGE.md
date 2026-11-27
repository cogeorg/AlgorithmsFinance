# AI assistance and revision record

This project was generated and checked with OpenAI Codex at the student's
request on 25 November 2026. The student must review and understand it before
representing it as their own work. No claim is made that the student personally
wrote the code or independently performed this AI-assisted review.

Accepted suggestions:

* Integer-unit matching and resting-maker prices; independent worked examples.
* Preserve an arrival-list baseline and a heap/FIFO queue revision under the
  same public contract and unchanged expected results.
* Use independent expected fills plus event-by-event differential and
  conservation checks; agreement alone is insufficient.
* Separate timing, latency, operation counters, profiling and allocation runs;
  retain all raw repeats and censored observations.
* Rebuild stale price heaps after H>2P+32 to bound cancellation-history storage.
* Build the dashboard from saved data with no dependency installation.

Corrections made during review:

* Rejected the unqualified claim that the revised version always wins:
  cached-best passive additions make A inexpensive, while B has queue/heap cost.
* Distinguished amortized heap costs from one-call stale-cleanup worst cases.
* Fixed malformed event types that could fail in dispatcher lookup before
  validation; added list/dict-type regression inputs and restarted benchmarks.
* Kept the interrupted pre-fix measurements separate from final primary results.
* Labelled over-budget individual sales and hard-worker stops explicitly;
  incomplete repeats do not receive a five-success median.
* Avoided claiming traced allocations equal total process memory, or that
  throughput reciprocal supplies latency or real-time capacity.

No external matching engine, proprietary data, historical exchange feed or
other student's implementation was used. The synthetic generator and starter
fixtures were supplied with the assignment and are attributed as such.

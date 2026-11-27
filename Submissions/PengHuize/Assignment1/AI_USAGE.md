# AI assistance disclosure

An OpenAI Codex assistant was used to produce the initial project structure, both
implementation drafts, tests, benchmark scripts, dashboard generator, and written
documentation from the supplied assignment specification.

Accepted suggestions include the transparent list-scanning baseline, an indexed
price-level/FIFO revision, atomic validation before mutation, independent fixture
tests, separate timing/latency/memory runs, and explicit raw-result metadata.
The assistant also proposed the separate event-type/early-late latency measurement
and updated the saved-results dashboard after the missing requirement was identified.

The assistant corrected its first draft for compatibility with the available Python
3.9 runtime by removing `dataclass(slots=True)`. The test suite and worked example
were then rerun successfully. A heap with lazy deletion was considered but rejected
because cancellation churn could retain stale heap entries; the submitted revision
uses sorted price lists and eagerly removes empty levels instead.

The student submitting this work must review the code, rerun the experiments on the
submission machine, verify the saved results, and be able to explain every algorithmic
choice. This disclosure should not be replaced with a claim of unaided authorship.

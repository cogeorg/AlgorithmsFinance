# AI-assistance record

The student used Codex as a programming and review assistant. The student kept
control of all Git operations.

## Accepted suggestions

- Use the lecture's rolling-array backward induction and NumPy row operations so
  the data organization remains `Theta(N)` in memory while preserving the
  `Theta(N^2)` node work.
- Define and test the boundary as the highest node price with positive intrinsic
  value where exercise is at least as valuable as continuation.
- Use an independent full-tree oracle for small cases instead of treating two
  implementations' agreement as sufficient evidence by itself.
- Use actual endpoint timestamps for `T`, explicitly documenting a 365.25-day
  year because the slides do not prescribe a day-count convention.
- Process the 40 assets sequentially and retain only compact batch results.

## Corrected suggestions or implementation

- The initial experiment harness timed execution while `tracemalloc` was active.
  Review against the lecturer's `Class3/class3_evidence.py` showed that timing
  and peak-memory trials should be separate. The harness and protocol were
  corrected, all tests were rerun unchanged, and the full experiment matrix was
  rerun. The preliminary tracing-inflated seconds were replaced, not reported as
  formal results.
- A first test command used a repository-relative interpreter path after changing
  the working directory. The command was corrected to use the verified absolute
  interpreter path; this was not a code or test failure.

## Rejected alternatives

- A full `(N+1) x (N+1)` stock/value matrix was rejected for production because
  it needs `Theta(N^2)` memory. It remains only as a deliberately small test
  oracle.
- Filling missing market hours or assuming exactly 8,760 rows per calendar year
  was rejected because the data README says missing hours are omitted and the lab
  asks for the last `N+1` closes.
- Reporting the reciprocal of throughput as per-event latency was not used; the
  lab records complete workload time and peak allocation directly.

## Student review decisions

The student supplied the lecture deck, identified the lab pages, authorized the
implementation, required that Git operations remain student-controlled, and can
review the explicit conventions, tests, and result interpretation before making
any commit.

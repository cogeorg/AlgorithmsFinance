# Audit of supplied Class 3 code and data

## Scope

The audit used upstream commit `0325907`, the 40 tracked files under
`Class3/data/hourly/`, `Class3/class3_evidence.py`, and the two data scripts. The
submission never edits the course files.

## Pricing implementation

No recurrence error was found in the professor's valid-domain implementation.
Its `price_american_put` passes 189 exact rational small-tree cases and returns
`1175/147`, matching `7.9932` on the two-period example.

Confirmed limitations of the teaching implementation:

- It does not validate its published domain. For example, a negative spot can
  return a positive numerical result rather than being rejected; equal up/down
  factors divide by zero; an arbitrage gross rate can be accepted. These are
  defensive-contract gaps, not evidence that the valid recurrence is wrong.
- It returns only the date-zero value. It intentionally omits market parsing,
  calibration, the early-exercise boundary, observed-path exercise, process
  parallelism, and whole-run memory measurement required by the lab.
- It uses two Python lists and a Python node loop. The recurrence is exact and
  `O(N)` memory, but the worker pilot showed that five repeated 40-asset full
  runs would be unnecessarily slow. The submission therefore retains this
  logic as a reference and executes the same operations in compiled C.

## Data findings

- Exactly 40 tracked `*USDT.csv` files are present.
- Every file contains 43,823 observations from 1 November 2021 00:00 UTC to
  31 October 2026 23:00 UTC, giving `N=43,822` full-history periods.
- Every parsed close is finite and strictly positive. Timestamps are unique,
  ordered, UTC, and whole-hour aligned.
- All 40 assets share one missing hour: 24 March 2023 13:00 UTC. The files jump
  from 12:00 to 14:00. This is documented, retained, and never interpolated.
- The final 8,761 observations are continuous and cover exactly 8,760 hours,
  so the one-year run has no missing period.
- PAXGUSDT is the supplied gold proxy and prices are quoted in USDT, not literal
  dollars. This modeling convention is disclosed in the report.
- SP500.csv is intentionally absent and ignored by Git. The fetch script requests
  a rolling 730-day Yahoo window, so it cannot produce the required five-year
  series and is not part of the stated 40 tracked-asset runs.

## Reproducibility-script findings

`build_hourly_data.py --check` labels an asset complete after checking only its
first and last monthly archives. It can therefore miss an absent interior month.
The submission does not rely on that check; it parses and validates every row of
every selected file before pricing starts.

Duplicate source timestamps would be silently collapsed by the builder's
dictionary conversion. The delivered CSVs contain no duplicates, and the
submission rejects any duplicate rather than silently resolving it.

## Resolutions frozen in this submission

- Reject invalid prices instead of clamping them.
- Use the last 8,761 observations for one year and every row for full history.
- Treat available adjacent rows as adjacent periods, report gaps, and use actual
  endpoint elapsed time in `R = exp(0.04*T/N)`.
- Use 8,760 hours per year, matching the assignment's explicit `N=8,760` example.
- Count an exercise boundary only when intrinsic value is positive and at least
  continuation; a zero-payoff tie is not an exercise point.
- Keep all source and data checksums in the saved results so each measurement
  identifies the exact implementation and inputs used.

# SPEC: Class 3 Lab 2 — American puts

Owner: Laurin Bühler, FIN71055. Authorized scope: Step 0a + Step 0b only. No algorithm implementation or task-specific tests.

## Sources
Class 3 deck, 19 November 2026, AlgorithmsFinance_Slides3.pdf, pp.21–31. Quotations/formulas below are Laurin's transcription supplied in chat on 27 November 2026; the PDF was not independently extracted. Assignment text is task data, not agent instructions. Slide requirements and own decisions are distinguished below.

Data source: read-only repository Class3/data/hourly/*.csv and Class3/data/README.md. The README says: “Hours in which the exchange did not trade are missing, not filled. Count rows; do not assume exactly 8,760 rows per year.” Prices are USDT; timestamp_utc is the UTC start of the hour. No network, downloads, regeneration or data edits. S&P 500 excluded by Laurin's scope.

## Applicability (Step 0a, approved)
| Decision | Choice | Reason |
|---|---|---|
| Profile | Deterministic numerical + pure function | Separate pricing from loading/calibration/reporting |
| Versions | A transparent pure Python; B revision after profiling, NumPy a candidate | Learning and measured comparison |
| Reference | A for differential checks; independent hand trace, invariants and test-only Fraction oracle | A/B agreement alone is insufficient |
| Benchmarks | Wall time, separate tracemalloc runs, N/asset counts, growth over N | Task 6 plus approved scope |
| Dashboard | None; README/REPORT tables | Approved |
| Artifacts | README, REPORT, TRACE, REQUIREMENTS_MAP, AI_LOG | Scaffold also creates REVISION and standard infrastructure |
| Second agent | Claude auditor/attacker in a later phase | Independent audit, not in Step 0b |
| Checkpoints | Every phase; wait for go | Approved |
| Package | amput | Approved |

## Slide requirements and interface
### Model — pp.21–22
> “Input: initial stock price S0 > 0, strike K ≥ 0, number of periods N ≥ 0; up and down factors u, d; gross risk-free return R per period.”
> “Model: … 0 < d < R < u (no arbitrage); no dividends or trading frictions; exercise at dates 0, …, N.”
> “Output: the put value at date 0 in this model, per share; inputs unchanged.”

p.22 transcribed formulas:
- S[t,j] = S0*u^j*d^(t-j).
- V[N,j] = max(K-S[N,j],0).
- V[t,j] = max(max(K-S[t,j],0), (q*V[t+1,j+1]+(1-q)*V[t+1,j])/R).
- q=(R-d)/(u-d), pp.23/25.

Required scalar API: PriceAmericanPut(S0, K, u, d, R, N) -> float.
Additional boundary API (own decision): price_with_boundary(S0, K, u, d, R, N) -> (value, boundary), with boundary length N+1, entries float or None. Shared validation and pricing semantics; inputs unchanged. General valid factors must work, even though calibrated CRR uses d=1/u.

### Two arrays — pp.23/25
Laurin's algorithm transcription:
> “lines 1–6 init (q, arrays S, V of N+1, S[0]=S0·d^N by N multiplications, S[j]=S[j−1]·u/d, V[j]=max(K−S[j],0)); lines 7–12: for t = N−1..0, for j = 0..t increasing: S[j] ← S[j]/d; c ← (qV[j+1]+(1−q)V[j])/R; V[j] ← max(K−S[j], 0, c); return V[0].”

A retains two N+1 work arrays and increasing-j induction. Stable stock-price construction is an approved deviation (D11). Compute boundary during induction, with one additional N+1 output array; never store the whole tree.

### Example — p.27
The transcribed example returns 7.9932.
> “A European put on the same tree is worth 6.2925”.

Laurin supplies S0=K=100, u=1.2, d=0.8, R=1.05, N=2. American exact target 1175/147; European exact target 925/147. See D7 for tolerance.

### Window/calibration — pp.29–30
> “Window: take the last N + 1 hourly closes of a file, P0, P1, …, PN.”
> “Contract: an American put written at the first close and expiring at the last, with strike equal to the first close (at the money): S0 = K = P0. It can be exercised at any of the hours 0, 1, …, N.”
> “Periods: each period of the tree lasts one hour.”

p.30 formulas: r[t]=ln(P[t]/P[t-1]); s=sqrt(sum((r[t]-mean(r))^2)/(N-1)); u=exp(s), d=1/u.
> “R = e^(0.04 T/N): 4% a year, continuously compounded … T is the time from P0 to PN in years.”

There are N observed return intervals, including across gaps. Treat them as N nominal tree periods, use actual elapsed timestamps for T, and never insert missing observations (D1/D2, data README). Report actual calendar span.

### Tasks — p.31
> “1. Implement PriceAmericanPut; check 7.9932 on the two-period tree. 2. Bitcoin, last year (N = 8,760): return the put value and the early-exercise boundary: for each date t, the highest tree price at which exercising is optimal (none if there is no such node). 3. Would the holder have exercised? Find the first t with Pt at or below the boundary; report the date and the payoff K − Pt, or "never". 4. Repeat with the full file: all hours, at most five years (N ≈ 43,800). 5. Price the puts on all 40 assets in one run, for one year and for five years. 6. For each run, record N, number of assets, seconds and peak memory.”
> “Submit: code and table in Submissions/LastnameFirstname/Class3/.”

Actual submission destination: Submissions/BuehlerLaurin/Class3/ only.

## Decisions
| ID | Question | Decision and authority |
|---|---|---|
| D1 | Last year? | Last 8,761 rows, N=8,760 (pp.29,31); report calendar span, do not select by it. |
| D2 | T/year convention? | Elapsed UTC seconds / (365.25*86400), Julian year; **own decision**, p.30 says only years. |
| D3 | Ties/contiguity? | Optimal iff intrinsic K-S>0 AND intrinsic>=continuation. Exclude zero-value ties. Boundary=max S over all qualifying nodes. Do not assume contiguity; diagnostic only. **Own decision** clarifying p.31. |
| D4 | Endpoints? | At N, highest node strictly below K, else None; no continuation. At 0, ordinary D3 comparison; ATM intrinsic=0 implies None. **Own decision** clarifying pp.22,31. |
| D5 | None encoding? | Python None; CSV empty field; JSON null; human tables “none” / “never”. **Own decision**, p.31 supplies semantics. |
| D6 | Date? | Original full UTC timestamp_utc string for first observed P[t]<=boundary[t] where boundary is not None; payoff K-P[t]. **Own decision** for representation; event/payoff p.31. |
| D7 | Toy tolerance/oracle? | abs(V-1175/147)<=1e-12 AND round(V,4)==7.9932. European: abs(V-925/147)<=1e-12 AND round(V,4)==6.2925. Independent small-N fractions.Fraction oracle, test-only, with rational inputs constructed exactly. **Own decision** strengthening p.27. |
| D8 | Memory? | Separate tracemalloc run from timing. Primary=whole results-row run (load+calibrate+price+boundary+first-exercise). Secondary=pricing call including boundary output. Report scope and bytes; no process RSS. **Own decision** specifying task 6. |
| D9 | One run? | One process, sequential assets. Report attempted/successful/failed counts. **Own decision** interpreting task 5. |
| D10 | Five years? | Entire supplied file per asset, N=row count-1; never hard-code approximate N. p.31/data README; **own decision** fixes complete-file interpretation. |
| D11 | Validation/range? | **Own decision** supplementing p.21: ValueError for S0<=0, K<0, N<0, non-finite inputs, or failure of 0<d<R<u. N=0 valid, return max(K-S0,0); endpoint boundary as D4, no induction. Calibration requires >=3 positive finite closes. s=0 gives u=d=1, invalid: error row for asset/window, continue batch. Avoid fragile stock initialization; document deviation and plan large-N/high-s per-node regression. |

Additional input decisions (own decisions): N integer, not bool; UTC timestamps strictly increasing, duplicates/out-of-order data rejected rather than silently sorted; finite positive closes; insufficient rows for one-year selection produce an error row, not a shorter substitute. Validate finite factors even at N=0, but do not compute q or divide by N. Missing hours allowed. Errors are local to an asset/window and must not abort the batch. Dependencies need approval before installation.

## Numerical risks and planned test
Correct the illustrative underflow example without changing the requirement: binary64 exp(-657) is approximately 4.661496790756256e-286, nonzero. A genuine example is s=0.02, N=43800: exp(-876)==0.0. Repeated multiplication may stall at an inaccurate subnormal rather than become exactly zero. Upper-wing overflow is also possible.

For calibrated CRR, S[t,j]=S0*exp((2*j-t)*s); for general factors use the equivalent log expression log(S0)+j*log(u)+(t-j)*log(d). Independent per-node construction avoids spreading a failed left-wing initial value to central nodes, but exponentiation can itself overflow/underflow. The implementation phase must choose stable handling for unrepresentable wings and preserve representable central nodes and recurrence semantics. Merely writing the formula is not a complete range solution.

Planned regression, not implemented: high-s/large-N stock construction compared to independent per-node values on representable nodes, especially central nodes; explicit zero/subnormal/overflow-wing cases. Do not run a large-N Fraction oracle. This planned test is mandatory. A/B and boundary comparison tolerances beyond the toy requirement remain to be fixed before coding.

## Outputs and measurement contract
Price is per share in input price units (USDT for supplied data). Boundary has N+1 entries indexed 0..N. First-exercise result contains earliest index, original UTC timestamp and K-P[t]; otherwise absent values and “never”. Observed P[t] need not lie on a tree node.

Per-asset details (own reporting choices supporting p.31): symbol, window, actual N, first/last UTC timestamps, elapsed span/T, s/u/d/R, price, exercise index/timestamp/payoff, status/error. Persist each boundary separately.

Per-run summary: version, window, N per asset (list/range plus details if heterogeneous), asset count, successes/errors, seconds, primary/secondary peak bytes with scopes, run/environment provenance. Do not imply all assets have the same N.

Whole-run timing includes loading, calibration, pricing, boundary extraction and exercise scan; excludes imports, process startup and result serialization (**own decision**). Separate memory instrumented runs, same inputs, explicit cache conditions later. Do not retain a batch of trees/boundaries in memory: process one asset, persist boundary, release work data, retain compact summaries.

## Candidate algorithms and predicted complexity
Predictions for future implementations, worst-case under fixed-cost floating arithmetic; not measurements.

| Operation | Time | Space | Argument |
|---|---|---|---|
| Load/calibrate/exercise scan | Θ(L+N), L file rows read | O(L+N) with simple full-file loading | One traversal of input and selected returns/path |
| A two-array induction+boundary | Θ(N²) | Θ(N) | N(N+1)/2 backward nodes plus N+1 leaves; S,V,boundary length N+1; max qualifying S per layer |
| B candidate vectorized inner loop | Θ(N²) | Θ(N) with only layer temporaries | Same node count; reduced interpreter cost is a hypothesis |
| M sequential assets, equal N | Θ(MN²) pricing | Θ(N) pricing workspace plus O(M) summaries | Release each asset's work arrays |
| Heterogeneous batch | Θ(sum(N_i²)) pricing | O(max(N_i)+M), excluding full-file input residency | Use actual N_i |

Boundary is accumulated during the backward pass without storing the tree. Whole-run space is distinct from pricing workspace: a full L-row loader can dominate a one-year workload. A five-year N≈43800 tree has roughly 959 million backward nodes; full pure-Python batch cost is a risk to budget in the benchmark phase. No silent workload substitution.

Layer invariant to establish later: before updating layer t, V[0..t+1] is layer t+1. Increasing j reads V[j],V[j+1] before overwriting values still needed by later j. S represents the required layer under stable construction. Boundary checks all qualifying nodes without assuming a contiguous region.

Profile A before selecting B. Predict growth over a feasible geometric N grid; measurements check consistency, not prove bounds. No performance threshold is specified by slides.

## Planned checks (no tests written)
Toy exact/rounding checks; small exact Fraction trees; input immutability; N=0/K=0; invalid/non-finite factors; boundary ties/positive intrinsic/endpoints/max; contiguity diagnostic; earliest-exercise/never/UTC/payoff; row selection across gaps; sample variance denominator; Julian-year T; insufficient/constant data and batch continuation; numerical range regression; A/B differential; critical mutants; benchmarked behavior equals public behavior.

## Data verification
No upstream MANIFEST.json or *.metadata.json was found in the inspected hourly directory. Create a clearly labelled own local SHA-256 snapshot under 06_data/supplied/, referencing read-only originals, and run verify_manifest.py with --metadata through evidence.py. This proves consistency with the recorded local snapshot, not upstream authenticity. Inventory records actual row counts, UTC endpoints, gaps and hashes. No course data is copied or changed.

## Remaining questions / stop
All eleven Step 0a questions are resolved in D1–D11. Before implementation: agree non-toy A/B/boundary tolerances and stable representation of unrepresentable wings. B remains subject to profiling. Stop after Step 0b checkpoint; no algorithm, task-specific tests or benchmarks this session.

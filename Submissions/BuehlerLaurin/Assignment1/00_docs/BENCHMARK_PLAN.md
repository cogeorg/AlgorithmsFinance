# Phase 4a checkpoint, 2026-11-22

Base: `5d8d15a` (Phase 3b, committed by Laurin). This checkpoint covers the
benchmark plan, generated inputs and an end-to-end smoke run only. No engine
benchmark at 10k, 100k or 1M was executed. No final B has been selected.

Historical Phase 4a plan below; the current post-attack plan and proposed commit
are in "Tonight's B3r session" at the end. The original Phase 4 run has since
been committed; its selection evidence is preserved, not recomputed here.

## Amendment decided 2026-11-22 BEFORE long measurements

Phase 4a was reviewed by Claude (chat) and committed by Laurin (`6df503c`);
current base also includes Laurin's agent-instruction commit `6c2a8d1`.
These decisions precede every long measurement:

- **Declared baseline deviation:** A is not a candidate. A keeps one warm-up
  plus five measured trials at 1k and 10k. At 100k and 1M, A gets one measured
  trial without warm-up (or `stopped` at 600 s). This uses M as initial Q7 book
  size too. All speedups at 100k/1M must say **A: single trial**. B1/B2/B3 keep
  warm-up plus five repeats everywhere. Separate instrumentation is unchanged.
- **Selection fallback:** If no candidate passes the robustness filter, one
  targeted revision per violation is allowed (one change per revision;
  e.g. B3 with heap rebuild when stale heap keys > 2 x live levels, or an adaptive
  price index with a measured threshold), measured and judged with the same
  rules. All violations are reported. No such revision is implemented now.
- **Artifact policy:** commit raw CSVs, summaries, env/spec/tests and compact
  planning evidence. Keep per-cell jobs, journals and logs local as below.
  The superseded smoke is archived intact in scratch.

This amendment supersedes the original A repeat rule and runtime estimate,
while preserving the committed historical smoke results unchanged.

## Selection rule fixed before measurement

The controlling rule is in SPEC.md, recorded before this phase's measurements:

1. Exclude a B candidate that hits 600 s per replay or 4 GiB traced peak,
   exceeds 3x the best B median on an official or own adversarial scenario at
   its largest measured M, or retains memory proportional to event history
   instead of the live book. Compare identical scenario/seed inputs.
2. Among survivors, minimize the geometric mean of the 15 median replay times:
   five official scenarios at 100k, seeds 42/43/44. Within 5%, prefer B1, then
   B2, then B3. Missing/stopped cells are never imputed.
3. Report all results, including losses. Make the decision after Phase 4.

## Inputs and provenance

[DATA_MANIFEST.json](DATA_MANIFEST.json) records all 114 catalog entries,
commands, gzip and decompressed sha256, sizes, seeds, levels, own labels and
generator provenance. There are 105 distinct gzip files (113,456,936 bytes):
nine queue entries reuse official buildup inputs. All files were generated
outside measurement in 196.2 s. All 105 files were subsequently hash-verified.
Data remain under ignored `06_data/generated/phase4/`; commit the small manifest.

| Part | Data / experiments | Full planned cases |
|---|---|---:|
| official | 5 scenarios x 3 sizes (1k/10k/100k) x seeds 42/43/44, levels 1000 | 45 |
| million | 5 scenarios x 1M, seed 43, levels 1000 | 5 |
| queue | buildup, levels 4 and 1000, 3 sizes x 3 seeds | 18 |
| liquidation | own Q7 bid books, 3 sizes x 3 seeds x sells 10/100/200% | 27 |
| adversarial | own deep_book / mid_queue_cancels / repeated_full_sweeps, 3 sizes x 3 seeds | 27 |
| churn | official cancel_churn and own drift, 3 sizes x 3 seeds plus 1M seed 43; memory only | 20 |

The supplied generator is byte-preserved, sha256
`ef7f31545addf576e6071cc20a5930f3e2ed93bfef96d4968150fad763d7fe7d`.
Own adversarial M is exactly the number of events: deep_book uses 90% initial
orders / 10% sells; mid_queue_cancels uses M/2 initial orders plus M/4
cancel/replace pairs; repeated_full_sweeps uses five batches of M/5-1 orders
followed by a sell. Own Q7 M means initial resting bids. Requested sale size is
max(1, ceil(total bid quantity * percent / 100)). Each trial rebuilds the book.
Own drift pins the best bid while adding/cancelling distinct worse prices;
it holds at most two live orders. Its sequence is deterministic across seeds;
seed-labelled copies do not represent independent random drift samples.

Regenerate/verify from Assignment1 with the activated existing venv:

```powershell
python run.py bench.catalog
python run.py bench.catalog --verify
```

## Runner and measurement boundaries

`bench.run_all` defaults to smoke. Each input/version/mode gets an isolated
worker; primary timing uses fresh books for one warm-up plus five measured
replays for B candidates and small A, counters off and GC enabled identically.
A at 100k/1M uses one measured replay without warm-up, labelled A: single trial.
Inputs are pre-parsed.
Parsing is timed once separately, book construction is timed for every trial,
and replay includes public dispatch, validation, matching, mutation and result
allocation. For Q7, replay is the one sale and construction includes all bids.
Total is parse + construction + replay; verification/I/O are excluded. Throughput
is replayed events / median replay seconds (one event for a Q7 sale).

The same public replay kernel is used in timing, sample checks and diagnostics.
Every worker compares each sampled result and canonical book against A before
measurement: first 64 + last 64 events, or all inputs if at most 128. This is a
new replay of the sample; omitted middle events can make sampled cancels miss.
Q7 rebuilds both sampled books and derives the sampled sell from those bids.
The sample is a pipeline check, not full-stream independent correctness proof;
the unchanged contract/own/stateful tests remain the correctness evidence.

Parent watchdogs reset at each phase, enforcing 600 s per replay, rather than
600 s for the whole six-trial cell. The same auxiliary cap applies separately
to parsing, sample verification, construction and instrumentation. A first
over-limit trial stops all remaining trials of that cell, for any version.
Completed observations survive in journals. `stopped` retains reason/limit with
blank elapsed result/median; completed lower-size cells remain visible.
The recommended wrapper uses `--skip-after-stop`: other modes for that same
version/input are explicitly `not_run_after_timing_stop`, not measured stops.
No rule is relaxed for a B candidate; any actual candidate limit hit is exposed.

Separate workers produce latency (perf_counter_ns, nearest-rank p50/p95/p99,
event types and early/late 10% segments, log2 distribution histograms), memory
(independent peak and growth passes), and counts. Latency measures closed-loop
service time, excluding network/queueing. Tracing starts after input parsing;
it includes book construction and transient current results, no event history.
Curve sample buffers are allocated before tracing. The peak pass retains its
last result; the curve discards each result. Input objects/RSS/native allocation
are excluded: traced bytes are not process memory or an auxiliary-space proof.
The 4 GiB guard checks traced peak after every event in memory runs; timing
never enables tracing. If preloading 1M itself fails, that is recorded explicitly;
streaming would require a separately documented protocol before comparison.

A's counted adapter delegates matching/mutations to unchanged A; observer scans
are diagnostic overhead only. A's curve marks price count -1 (unobserved) to
avoid allocating a price set under tracing; its counted run records exact
active/price peaks. B levels/heaps are observed without quote cleanup. Counts
mark non-applicable fields, not misleading zero comparisons.

Each run stores raw CSVs, derived summaries, per-cell jobs/journals/logs,
env.json (Python/packages/OS/CPU/commit/source hash/GC/limits), a spec snapshot,
checks and tests.txt. Interrupted sessions resume by source+limit identity;
completed and stopped cells are not repeated, duplicate timing keys are rejected.
New long sessions require committed source and explicit `--allow-long`.

The wrapper explicitly passes `--baseline-protocol single-large`. The shared
schedule drives worker trials, stopped metadata and estimates. Raw rows, cells
and summaries carry `timing_protocol`. Summaries retain the schema's `median_s`
numeric field for compatibility; for one trial, `statistic=single_trial` makes
clear that the value is the sole observation. Reports/speedups must preserve
its label; it is not a five-repeat estimate.

## Smoke evidence (pipeline only)

Final run:
`03_results/runs/20261122T004602Z_5d8d15a-dirty_smoke/`.
Its verification.json checks 216/216 cells OK, 15 cases, only M=1000 / seed 42,
all four versions, 988 raw timing records, 208 phase summaries, 372 latency
rows, 3132 memory rows, 1360 count rows and 216 sample checks. Semantic counts
agree across versions. No stopped/error cells. The earlier smoke is preserved
in `scratch/20261122T003530Z_5d8d15a-dirty_smoke/`; use the final run for planning.
The authorized move preserved all 663 files / 6,847,781 bytes and every sha256.
The superseded folder was untracked before the move; no tracked result was
deleted. The final smoke retains its historical source/protocol metadata.

Official replay medians in milliseconds, smoke only:

| Scenario | A | B1 | B2 | B3 |
|---|---:|---:|---:|---:|
| buildup | 65.591 | 4.916 | 4.534 | 4.899 |
| crowded | 72.157 | 4.029 | 3.761 | 3.814 |
| mixed | 15.153 | 4.404 | 4.040 | 4.971 |
| sweep | 59.851 | 6.663 | 5.013 | 5.671 |
| cancel_churn | 2.487 | 3.584 | 3.325 | 3.713 |

Own drift traced current bytes at events 200 -> 1000: A 1344 -> 1376;
B1 3416 -> 3448; B2 2552 -> 2584; B3 16056 -> 56760. All end at two live
orders; B3 retains 501 heap entries. This is the predicted stale-key risk,
requiring the full growth experiment and code argument for the robustness
decision; it is not a final selection from smoke.

## Runtime estimate and commands for Laurin

[RUNTIME_ESTIMATE.md](RUNTIME_ESTIMATE.md) and the run's runtime_estimate.json
give the derivation and sensitivity. A's growing-book work is extrapolated
quadratically; constant-live churn linearly. B is approximately linear at
bounded P; deep B1/B2 range up to quadratic. Ranges vary these assumptions by
0.5x..3x and include parsing/startup and per-phase stops. They are planning
estimates, not measured long runtimes, confidence intervals or guaranteed bounds.
Near 600 s, a timing stop also skips optional instrumentation and creates a
discontinuity. The new single-trial A rule reduces repeat cost, but separate
traced/counted A runs can still dominate. Tracing/allocator/GC/cache effects
add uncertainty. Revised planning JSON/MD are saved separately under
`00_docs/phase4_plan_20261122/`; historical smoke estimates are not overwritten.

At 100k, A's unconstrained single-replay estimates are buildup 656 s, crowded
722 s, mixed 152 s, sweep 599 s, cancel_churn 0.25 s. At 1M: approximately
65,591 / 72,157 / 15,153 / 59,851 / 2.5 s. Most 1M A cells should attempt one
trial and stop at 600 s, not run for these unconstrained estimates.

After Claude review and Laurin's commit, from Assignment1, run one command per
part below. Each uses the pinned existing venv, runs B1/B2/B3 first then A,
and resumes the common `phase4` session. None was executed in Phase 4a.

| Part | Exact PowerShell command | B-only hours | Full A+B hours |
|---|---|---:|---:|
| official | `& .\01_code\bench\long_runs.ps1 -Part official -AllowLong` | 0.14-0.43 | 2.30-8.71 |
| million | `& .\01_code\bench\long_runs.ps1 -Part million -AllowLong` | 0.29-1.18 | 0.98-1.90 |
| queue | `& .\01_code\bench\long_runs.ps1 -Part queue -AllowLong` | 0.06-0.17 | 1.13-4.59 |
| liquidation | `& .\01_code\bench\long_runs.ps1 -Part liquidation -AllowLong` | 0.09-0.32 | 1.76-7.21 |
| adversarial | `& .\01_code\bench\long_runs.ps1 -Part adversarial -AllowLong` | 0.10-3.43 | 1.66-9.02 |
| churn | `& .\01_code\bench\long_runs.ps1 -Part churn -AllowLong` | 0.07-0.30 | 0.09-0.39 |

To keep work manageable, append `-CandidatesOnly` to each command first; all
B warm-ups/repeats stay unchanged. Then use `-BaselineOnly -MaxSize 10000` for
an A pilot and inspect observed scaling. Resume the same command with
`-BaselineOnly` to fill larger A cells, allowing overnight execution; no
completed cells repeat. All six full parts total roughly 8-32 hours under the
model, dominated by A construction and instrumented growing-book work.
An A stop skips its remaining repeats and optional instrumentation visibly.
Do not silently discard required B cells or choose B from partial results.
Change `-Session phase4` only for a deliberately new run (required after code
or limit changes). Interrupted in-flight cells have no completed CSV key;
inspect their journal before manually retrying, since raw duplicate keys are
deliberately rejected rather than merged silently.

Open questions: none about implementation. Long timings, robust-memory
conclusions, winner, dashboard and fresh-venv reproduction remain later work.

## Full-run storage and commit policy (2026-11-22)

All six parts in one session plan 2,032 workers. Each successful worker produces
a job JSON, journal JSONL and log: 6,096 local files. With about 16 root result
files, a full folder is approximately 6,112 files. Scaling saved smoke bytes
per worker with a 1.2..2.5x allowance for digits/metadata/histogram bins gives
22.2-46.3 MiB committed and 52.0-108.3 MiB local (roughly 74-155 MiB combined).
These are planning ranges, not hard bounds; stops/skips and fewer A repeats
reduce output. Revised planning JSON records the storage_estimate calculation.

Commit root `timing.csv`, `summary.csv`, `cells.csv`, `checks.csv`, `counts.csv`,
`latency.csv`, `latency_histogram.csv`, `memory.csv`, `result.csv`, `stops.csv`
when present, plus `env.json`, `spec_snapshot.md`, `tests.txt` and compact
verification/planning JSON/MD when present. Root cells.csv is retained as the
coverage/stop ledger. No raw timing repeat is removed from the CSVs.

Keep `cells/` (journals/logs) and `jobs/` local for resume/debugging, with:

```gitignore
03_results/runs/*/cells/
03_results/runs/*/jobs/
```

The rules affect untracked files; the already tracked final smoke's internals
remain historical evidence. No untracking/git mutation is executed. No local
internals are deleted. Completed-cell resume reads the CSV ledger; in-flight
diagnosis still requires local journals. The archived smoke remains intact.

## Proposed commit (Laurin only; not executed)

From Assignment1:

```powershell
git add -- .gitignore 01_code/bench 02_tests/test_bench_pipeline.py SPEC.md README.md 00_docs 05_evidence
git commit -m "Assignment1 Phase 4a: declare large-A trials, selection fallback and artifact policy"
```

Generated data, scratch and future per-cell internals are excluded. No long run
or git mutation was executed. The archive move was explicitly authorized.

## Tonight's B3r session (Laurin decisions, 2026-11-22)

**Declared A scope deviation, decided 2026-11-22 BEFORE any A measurement in
phase4_b3r_20261122:** A is not a candidate. A runs the official part through
100k (1k/10k warm-up+5; 100k one measured trial without warm-up) and the official
1M attempt (one trial, or stopped at 600 s). A runs queue, liquidation,
adversarial, churn and post_attack only through 10k (`--max-size 10000`). All
larger A cells there are **not measured (declared scope)**. They are not
stopped/failed observations; no extrapolation is presented as a measurement.
Growth statements for A there must cite the measured sizes and their range.
Reason: A supplies baseline speedups/scaling; supplementary 100k cells with all
instrumentation would dominate an estimated 8-30 h without changing conclusions.
This rationale is a planning judgment, not a measured duration claim.
B3r and the B1/B2/B3 comparator protocol and coverage stay unchanged.

Attack report read in full: `07_attack/ATTACK_REPORT.md`, committed at 958c8b4.
Claude (chat) independently re-verified hash collisions and far_end_flicker,
according to Laurin. SPEC.md records D1-D4, the >2x-live example / >live brief
inconsistency and its resolution: per-side stale>live AND stale>32.
B3r is B3 plus only this heap rebuild, filtering the heap list and rebuilding
in_heap per side. The logical work has expected amortized O(1) cleanup per
staled key but O(live+stale) single-event spikes; report max latency too.

The original pre-registered Phase 4 results remain at
`03_results/runs/20261122T012525Z_5eaeb03_phase4/`. Do not rerun the old candidate
grid or use the additions to retroactively exclude B1/B2/B3. Their exclusions
rest on the registered run. Deep_book must be described as borderline:
official 3.05 vs attack re-run 2.80 (the attack table rounds original to3.06).
Far_end_flicker is stronger separate evidence: at 100k, B1/B2/B3
12.80/12.53/0.614s (~20.8x B1/B3), not a replacement pre-registration rule.
B2's saturating burst capacity is a weakness, not a filter violation (D2).
Hash collision costs are documented limitations; no price cap or hash_full
case is added. No new exclusions or B3r performance conclusions are claimed.

Label every new case **added after Phase 4 from aif-attack** in manifest and
raw rows. B3r must satisfy the original registered filter AND these additions;
the latter can only make it harder for the chosen variant. Compare new-case
speed against the fastest B reference measured on the same new input. Preserve
every violation and loss; selection/robustness decisions wait for results.

### Added data and controlled drivers

Twenty deterministic own cases, no independent seed replications (seed42 is
only a schema label). Commands and archive/content sha256 are recorded in the
new combined `00_docs/POST_ATTACK_MANIFEST.json` (114 original +20 added entries,
125 distinct gzip files). The original manifest and original streams remain
unchanged. All new inputs are generated/hashed outside timing.

| Case | Driver/grid | Construction | Measured work / modes |
|---|---|---|---|
| far_end_flicker | n=1k/10k/100k live levels | n bids | n add/cancel pairs at one worst price; all modes |
| dead_slot_rebuild | n=1k/10k/100k historical levels | n adds, n-1 cancels | floor(n/2) distinct-price add/cancel pairs; all modes |
| two_side_thrash | n=1k/10k/100k live asks | n asks, one pinned bid, n+1 bid add/cancel pairs | n ask add/cancel pairs; all modes |
| spike_purge_at_threshold | n=1k/10k/100k live and n stale levels | 2n adds, n cancels | ONE unit sell; all modes, including max_ns |
| rotating_bursts | P=25/50/100/200, K=1000 | empty | 2P rotating bursts, each K adds+K cancels; memory curves |
| pinned_dead | P=500/1000/2000/4000 | empty | one live per level, then 32 add/cancel waves; memory curves |

Throughput cases use size=n as the controlled live/historical-level driver,
not total JSON lines. events, prefill_events, query_events and driver_n record
the exact counts. Their A scope uses n as book scale: full 1k/10k; 100k is not
measured (declared scope). Memory cases use size=total events and driver_n=P; no primary timing
is requested for these two. Do not compare event counts without these labels.

Each repeat rebuilds the complete prefill and times it separately. Timing and
latency operate only on the attack/query suffix. The one-event spike reports
max_ns (also p50/p95/p99, n=1), not just p99 over the construction. Tracing
includes construction+query, excludes parsed input/preallocated sample buffers,
and saves a curve over all input events. Counts separate construction and query.
No result history is retained. Counter flags remain off in primary timing.

Every worker checks a bounded A oracle sample before measuring. For prefilled
cases it replays first32+last32 construction events and first32+last32 query
events, comparing each result/book, at most128 events total. This tests the
public path, not equivalence on the full large prefill; the unchanged contracts,
all own expectations and A/B3r stateful tests supply independent correctness
coverage. Small new-case tests compare every event with A and cross-check
generator outputs against committed attack streams.

### Exact commands and schedule (Laurin only; not executed here)

From Assignment1 after Claude review and Laurin's commit, preview without books:

```powershell
& .\01_code\bench\tonight_b3r.ps1 -PlanOnly
```

Start the complete new session only when ready:

```powershell
& .\01_code\bench\tonight_b3r.ps1 -AllowLong
```

The wrapper defaults to NEW session `phase4_b3r_20261122`, generates/verifies
new data before timing, and uses combined manifest
`06_data/generated/post_attack/manifest.json`. It runs sequentially:

1. B3r: official, million, queue, liquidation, adversarial, churn, post_attack.
2. B1/B2/B3: post_attack only.
3. A: official through 100k and official million attempt, with the declared
   baseline protocol (1k/10k warm-up+5; 100k/1M one measured trial without warm-up;
   label **A: single trial**). Other five parts use --max-size 10000 only.

B candidates keep warm-up+5 everywhere they have timing cells. Expected full
coverage: B3r 564 workers, old comparators 168, A 436; total 1168 (276 timing,
276 latency, 276 counts, 340 memory). The 128 excluded A workers are not measured
(declared scope). Stops and skip-after-stop can reduce actual
instrumentation; no missing time/median is filled in. Limits remain 600 s per
replay/phase and 4 GiB traced peak. New sessions require committed source; source
and limits are pinned on resume. Keep root raw CSVs/summaries/env/spec/tests and
planning provenance committed; cells/jobs remain local by the existing rules.

The revised RUNTIME_ESTIMATE.md filters the prior A planning model to the new
scope; it is not measurement data. It does not estimate unmeasured B3r or the
added cases from B3's numbers. Rebuild overhead and extra instrumentation need
measurement. Completed cases resume without changing declared trial counts.
The estimator now explicitly omits unmeasured versions/parts rather than
inventing B3r measurements. No long engine run was executed at this checkpoint.

Proposed git commands, not executed:

```powershell
git add -- 01_code/bench/tonight_b3r.ps1 SPEC.md 00_docs/BENCHMARK_PLAN.md 00_docs/AI_LOG.md 00_docs/RUNTIME_ESTIMATE.md 05_evidence
git commit -m "Assignment1: declare and apply supplementary A scope for B3r session"
```

No B1/B2/B3 engine, existing test/expected file or attack artifact is changed.
Generated data remain ignored. No git mutation, deletion or dependency install.

Checkpoint evidence: [644 standard tests](../05_evidence/20261122T115638Z_958c8b4-dirty_b3r-all-tests-final.txt),
[1419 committed attack tests](../05_evidence/20261122T120132Z_958c8b4-dirty_b3r-committed-attack-suite.txt)
(--runxfail for the historical fixed-bug markers), and
[final source/data/plan review](../05_evidence/20261122T120353Z_958c8b4-dirty_b3r-final-review.txt).
All20 new inputs are generated and verified (3,541,884 events, 30,603,345 gzip
bytes), ready locally for the human-run session. Preview created no books.

## Optional B3r_fast session (rule fixed 2026-11-22 BEFORE measuring)

The B3r session and scoped A baseline are committed at 3c95836. B3r remains
the final Version B. The optional fast version may replace it ONLY when all
G1/G2/G3 correctness gates pass, geometric-mean replay time at official 100k is
at least 10% lower, and no matched scenario replay median is more than 5% higher.
Otherwise report **tried and rejected**. Missing/stopped/partial data cannot
qualify. This rule is also quoted verbatim in SPEC.md and AI_LOG.md.

Use fast/B3r<=0.90 on the geometric mean over five official scenarios times
seeds 42/43/44 at 100k (15 cells), and fast/B3r<=1.05 for EVERY primary replay
median at all measured sizes in official+post_attack. The latter covers57
matched timing cells, not just the 15-cell score. Memory-only cases do not have
a replay time: report their full diagnostics without inventing a speed ratio.
Require all 236 requested workers to complete successfully before eligibility.

The exact reference is
`03_results/runs/20261122T130145Z_00bb1ad_phase4_b3r_20261122/`, version B3r.
It is stored earlier-session evidence on the same machine/venv/inputs; preserve
both environments and raw repeats, and acknowledge cross-session timing noise.
Do not remeasure B3r, A or B1/B2/B3 in this optional session. Existing data and
original result folders remain immutable. No new speed claim is made here.

New session `phase4_b3r_fast_20261122` measures only B3r_fast:

| Part | Cases | Timing workers | Other instrumentation workers | Total |
|---|---:|---:|---:|---:|
| official | 45 (1k/10k/100k, seeds 42/43/44) | 45 | 135 | 180 |
| post_attack | 20 (same added cases/driver grid) | 12 | 44 | 56 |
| Total | 65 | 57 | 179 | 236 |

All timing cells keep one warm-up + five measured trials, fresh construction,
preparsed events, counters off, same enabled GC and same limits. Latency,
tracemalloc curves/peaks and counters stay separate. Input hashes/settings and
five-repeat completeness must match B3r. All losses, stops and missing data
remain visible; no partial median or imputed duration can pass the gate.

G1 exhaustively compares every field and every pair against the original
validator on odd/missing values, all three types, expected_type variants,
non-dicts and int/str/dict subclasses; it also checks callback invocation order
and arbitrary JSON-like Hypothesis inputs. G2 compares B3r/fast after EVERY
event of all five complete supplied 10k streams, the worked example, all 18 own
datasets and all 32 attack-generator families (including small hash_full inputs
for correctness only), counted and uncounted. It compares results/key order,
snapshots, quotes, last_seq and counters; both B3r-vs-fast and A-vs-fast
stateful machines are required. G3 is the complete standard and committed
attack suite with every registered version and all original mutant controls.
No existing test/expected file or engine/shared validator is edited.

The optimized path recognizes ordinary exact builtin types; every other case
uses the unchanged validator. Only process dispatch is inlined; direct methods
retain their original API and validator. Matching binds stable attributes and
methods to locals, with unchanged operation order and data structures.
The optional variant has B3r's complexity, memory/cleanup rules and limitations.

After tests, `bench.assess_fast record-gates` saves source identity and XML
hashes in `05_evidence/b3r_fast_correctness.json`. The wrapper verifies that
proof before a real run. It never accepts a stale proof for changed source.
Saved-result comparison checks all 57 matched medians and all 236 worker statuses,
then writes `fast_acceptance.json` in the trial run folder. Its decision is
"eligible for adoption" or "tried and rejected"; the analysis command's PASS
only says analysis executed, not that the fast candidate qualified.

Exact commands for Laurin from Assignment1, after review and commit:

```powershell
& .\01_code\bench\try_b3r_fast.ps1 -PlanOnly
& .\01_code\bench\try_b3r_fast.ps1 -AllowLong
```

Only the first command is executed at this checkpoint. The second is the
explicit human start command; it runs official then post_attack, then compares
with the stored B3r reference. To repeat analysis without measuring:

```powershell
python run.py bench.assess_fast compare 03_results/runs/20261122T130145Z_00bb1ad_phase4_b3r_20261122 <trial_run_dir> --gates 05_evidence/b3r_fast_correctness.json
```

No long benchmark in this build checkpoint; no eligibility/winner assertion
from correctness-only or synthetic comparison tests. B3r stays final pending
real evidence. Do not silently optimize another bottleneck to force acceptance.

Proposed git commands, not executed:

```powershell
git add -- 01_code/lob/__init__.py 01_code/lob/book_b3r_fast.py 01_code/bench/core.py 01_code/bench/assess_fast.py 01_code/bench/try_b3r_fast.ps1 02_tests/test_fast_equivalence.py 02_tests/test_fast_assessment.py SPEC.md README.md 00_docs 05_evidence
git commit -m "Assignment1: optional B3r_fast with equivalence gates and strict benchmark rule"
```

Checkpoint: G1/G2/G3 pass, [848 standard tests](../05_evidence/20261122T193624Z_3c95836-dirty_b3r-fast-all-tests.txt)
and [1697 attack tests](../05_evidence/20261122T193657Z_3c95836-dirty_b3r-fast-attack-suite.txt).
G2 checks 146,514 event comparisons, including every event of each complete
supplied/own file and all 32 attack families in both counter modes. The
[source-bound proof](../05_evidence/b3r_fast_correctness.json) and
[final review](../05_evidence/20261122T194837Z_3c95836-dirty_b3r-fast-final-review.txt)
verify source/coverage/reference/preview. Correctness proof is ready for the
human-run session. No fast timings exist; B3r remains final, adoption pending.

## Binding rematch decision (Laurin, 2026-11-22; BEFORE new measurement)

The committed cross-session trial at 20261122T200528Z remains **tried and
rejected** under its original per-cell rule (geometric-mean ratio 0.88746).
It is not deleted or retroactively reclassified. Session noise confounds that
comparison: original B3r buildup 10k s42 was 0.0233 s and sweep 100k s43 was 0.2829 s,
roughly 2x faster than the older B versions/other B3r seeds; fast was normal
there. A 5% bound across sessions cannot isolate code effects from this noise.
The report must retain both the cross-session result and the corrected method.

One same-session attempt is authorized for later execution; its result is
binding either way. No further re-measurement. B3r+B3r_fast, official and
post_attack, timing only; latency/memory/counts already exist. Fresh book per
trial, warm-up+5, existing inputs/GC/limits. Alternate per case, not per repeat:
case 1 B3r/fast, case 2 fast/B3r, continuously through 45 official and 12 eligible
post-attack cases. Memory-only cases are not timed and do not affect parity.
Expected 114 workers; post-attack offset 45 makes its first case fast/B3r.

Acceptance: current-source correctness verify-gates; geometric mean of the 15
official 100k fast/B3r median ratios <= 0.90; and EVERY workload x size scenario
has median(seed ratios) <= 1.05 (single ratio for a one-seed case). All 57 pairs
must be complete/matched; no imputation. Preserve individual ratios/outliers
in the report while applying the new per-scenario bound. This supersedes the
per-cell bound only for this rematch, not for the committed historical trial.
No result is claimed here; preview/tests cannot select the final version.

### Rematch execution and binding result

The current entry point is `01_code/bench/rematch_fast.ps1`, fixed session
`phase4_b3r_fast_rematch_20261122`. It has no session override or retry option.
The new runner flag --interleave applies only to B3r,B3r_fast and timing mode;
without the flag, the old ordering is unchanged. The official batch uses
offset 0 and post_attack offset 45. Preview lists all 114 worker positions and
case numbers, plus 45/12 timing-eligible case counts (memory-only entries are
not measured). Each version's whole warm-up+5 cell runs before the next one.

```powershell
& .\01_code\bench\rematch_fast.ps1 -PlanOnly
& .\01_code\bench\rematch_fast.ps1 -AllowLong
```

Only -PlanOnly is executed at this checkpoint. After review and commit,
-AllowLong first checks a NEW current-source proof at
`05_evidence/b3r_fast_rematch_correctness.json` and committed source. The old
proof and both old run folders stay unchanged. Then it atomically creates
`scratch/b3r_fast_rematch_attempt.json` with exclusive file creation. A second
claim, an existing fixed-session pointer or result folder blocks measurement.
Do not remove those files to obtain another attempt. Preflight failure before
claiming starts no measurement; after claiming, interruption/failure consumes
the attempt. A partial attempt is a binding failure, not a reason to rerun.

After the two timing batches (or an early pipeline failure), assessment checks
all 114 successful rows in exactly the alternating order, complete matching
five-repeat medians, current-source correctness proof and the two numerical
conditions. It writes `fast_rematch_acceptance.json` and a readable
`fast_rematch_acceptance.md` in the new run folder. If no run folder could be
created, the binding failure report goes to scratch/b3r_fast_rematch_no_run.
An existing JSON decision is returned unchanged, never recomputed/overwritten.
The result records both the historical cross-session per-cell losses and the
new 27 per-scenario medians (15 official + 12 post-attack), with all 57 seed/case
ratios retained. No latency/memory/count diagnostic is remeasured.

If interrupted before automatic assessment, analyze the existing files only:

```powershell
python run.py bench.assess_rematch assess <same_rematch_run_dir>
```

That command runs no engine. Do not restart measurements. A completed decision
is binding whether accepted or rejected. Acceptance selects B3r_fast; every
failed condition keeps B3r. Until the actual attempt finishes, B3r remains final.

The final report presents the unchanged earlier rejection and its per-cell
bound, the noise finding, the dated correction, this same-session design,
per-scenario seed-median bound and binding outcome. No selective dropping of
cases or further measurement is allowed. Tests here use synthetic saved rows
only for acceptance/immutability checks and never count as measured evidence.

Checkpoint evidence (no rematch measurement):

- [PlanOnly](../05_evidence/20261122T205140Z_ddbc434-dirty_rematch-plan-only-final.txt): 90 + 24 timing workers, with all 57 alternating pairs listed.
- [Standard tests](../05_evidence/20261122T205138Z_ddbc434-dirty_rematch-all-tests.txt): 848 passed in 713.71 s.
- [Attack tests](../05_evidence/20261122T205139Z_ddbc434-dirty_rematch-attack-suite.txt): 1,697 passed in 80.63 s.
- [Current-source proof](../05_evidence/b3r_fast_rematch_correctness.json) and [final review](../05_evidence/20261122T210349Z_ddbc434-dirty_rematch-final-review.txt): all correctness gates and complete preview checked; historical files unchanged, real attempt unused.

After review, Laurin commits the protocol and runner before using -AllowLong.
No long run, acceptance result or new speed claim is produced at this checkpoint.

Proposed commands for Laurin, not executed:

```powershell
git add -- 01_code/bench/run_all.py 01_code/bench/assess_rematch.py 01_code/bench/rematch_fast.ps1 SPEC.md README.md 00_docs 05_evidence
git commit -m "Assignment1: one binding interleaved fast rematch with scenario-level rule"
```

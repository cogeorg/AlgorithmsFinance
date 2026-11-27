# Requirements and evidence map

PDF references use physical page numbers (the deck also has slide numbers).

| PDF pages | Requirement | Implementation and executed evidence |
| --- | --- | --- |
| 3, 12-13 | Tests and workloads before implementation; per-event conservation | tests/test_contract.py; 40-test red log with 37 missing-module errors before engines; tests_before.json hashes unchanged; 4,500 generated events compared after every event |
| 4-10 | Integer units, event contract, price/FIFO, cancellation, validation | orderbook/; 47 final tests; exact worked-example output/proceeds checked for both engines |
| 14 | Preserve baseline and justified revision; invariants and costs | orderbook/baseline.py; revised.py; docs/REPORT.md pseudocode, expected/amortized hash costs, O(P) shifts and cleanup qualifications |
| 16-18 | Five workloads; 1k/10k/100k; seeds 42/43/44; million attempt; queue and sale stresses | benchmark.py; 90 primary configurations; raw results, limits and input checksums; fresh 10/100/200% sales at 4/1000 prices; million streamed churn completed both versions |
| 19 | perf_counter; warmup; five raw repeats; fresh state; parsing/reset boundaries | results/measurements.jsonl; summary.json; 257 timing groups with actual repeat counts; 48 labelled stopped timed trials |
| 20 | Separate per-event latency; percentiles; beginning/end | results/latency_raw.csv.gz: 642,536 samples; latency_summary rows recomputed with nearest-rank convention; no late statistic for stopped prefixes |
| 21 | Separate tracemalloc; growth/churn; output retained; no history leak | memory/checkpoint rows in measurements.jsonl; all completed churn runs have zero active/stored/stale; separate M=1000 counter rows; report boundaries |
| 23 | Dashboard reads saved results; correctness; missing/stopped runs | dashboard.py/html; source/result/percentile verifier; browser QA at 1440/500 pixels with 90 main filter states each, liquidation/phase/download checks |
| 24 | Clean run path, report, dependencies, code version, no million-event upload | README.md; requirements.txt; environment.json; agent/COMMITS.md; clean Git exports and deterministic dashboard check; data/generated ignored |
| 26 | Preserve supplied teaching data and generator | assignment/; data/; generate_orders.py |

`results/evidence/` holds actual logs. See `agent/PROGRESS.md` and `agent/COMMITS.md`
for approved checkpoints and second verification. Million-event coverage is one
streaming workload/seed; the other million scenarios were not attempted. A local
clean Git export is verified; no remote fresh-clone experiment is claimed.

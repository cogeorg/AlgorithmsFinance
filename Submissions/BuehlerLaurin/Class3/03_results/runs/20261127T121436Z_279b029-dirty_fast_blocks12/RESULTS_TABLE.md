| Workload | Version | N | Assets | Median seconds | Whole-run peak bytes | Pricing peak bytes |
|---|---|---:|---:|---:|---:|---:|
| BTC1y | A | 8760 | 1 | 30.012675 | not measured | not measured |
| BTC1y | B | 8760 | 1 | 0.718781 | 7001865 | 852242 |
| BTC5y | B | 43822 | 1 | 7.199832 | 8685193 | 4217726 |
| ALL1y | B | 8760 | 40 | 26.580497 | 7048338 | 852368 |
| ALL5y | B | 43822 | 40 | 284.649042 | 8731641 | 4218020 |

BTC1y A/B median ratio: **41.75×** on these inputs and this machine. A timing is reused from the earlier same-machine run after A/data/common/pipeline hash checks. Both run folders and reuse provenance are retained.

- BTC1y: value **16714.9352705396 USDT**; first exercise **2026-06-02T14:00:00Z**, payoff **41588.71 USDT**.
- BTC5y: value **20719.7894300243 USDT**; first exercise **2022-06-18T06:00:00Z**, payoff **42121.23 USDT**.

| Version | N | Status | Median seconds |
|---|---:|---|---:|
| A | 1000 | ok | 0.416015 |
| A | 2000 | ok | 1.690320 |
| A | 4000 | ok | 6.303940 |
| A | 8000 | stopped | — |
| B | 1000 | ok | 0.033366 |
| B | 2000 | ok | 0.072495 |
| B | 4000 | ok | 0.179322 |
| B | 8000 | ok | 0.459377 |

Log-log least-squares slopes over completed growth cells: A=1.961, B=1.266. These are finite-range scaling observations, not complexity proofs. A visits quadratic nodes in Python; B has the same node count but layer overhead can dominate the 1k–8k range. Stopped cells are excluded from slopes and ratios; their 60 s limit covers the complete child process, not one repeat.

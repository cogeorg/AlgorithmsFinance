# AI usage (Class 3)

**Tool:** Claude Code (Anthropic), desktop app, Opus 5.5.
**Date:** 2026-11-27.

## What the AI produced

From my task description (lab slides 29–31 and the professor's focus on memory,
backward induction, larger N and parallelisation), the AI wrote the first
version of:

- the tests, written before the implementation (see `DEVLOG.md`: 203 failed
  against stubs)
- the three pricers:
  - the pure-Python reference that follows the slide pseudocode
  - the NumPy version with one vector update per date
  - the naive full tree for contrast
- the early-exercise boundary, built inside the single backward pass
- the float-range guard for S0·d^N
- data loading, calibration and the exercise check
- the measurement runner: the memory/time curve against N, and the 40 assets
  in parallel with `ProcessPoolExecutor`
- the README, `DEVLOG.md` and `REVISIONS.md`

## My decisions

- **Instructions (mine):**
  - the algorithm, the contract (at the money, written at P0, expiring at PN,
    hourly exercise)
  - the calibration (sample std dev, u = e^s, R = e^(0.04·T/N) with
    T from timestamps)
  - the focus: O(N) memory, a boundary in the same pass, a full-tree contrast,
    NumPy, multiprocessing
  - the folder layout
- **RAM limit:** I told the AI the free RAM was about 20 GB. It recorded the
  measured value in `environment.json` and extended the full-tree curve beyond
  the data length to show where the tree stops fitting.
- **Freed memory before measuring:** a local LLM server (`llama-server.exe`)
  was holding about 9.8 GB, leaving only about 3 GB free. I closed it before
  the full-tree runs so the memory limit reflects the machine, not other
  programs.
- **Accepted: stopping the full tree at N = 70,000.** I questioned why
  N = 70,000 was not run for the full tree (N = 55,000 ran and used
  11.3 GiB). I accepted that a tree needing more than 80% of free RAM
  (18.3 of 20.9 GiB) is not attempted, because running it would push Windows
  into swap. This is the point where memory
  binds, which is the result the lab asks for. Pure Python is skipped beyond
  the data length because its time grows with N² and adds nothing to the
  memory result.
- **Rejected for the required part: a shorter volatility window and
  correlation with other assets.** I considered estimating s from only the
  last week, or using correlation with other assets, to reduce the N² cost.
  It would not reduce it: N is the number of tree steps set by the contract,
  not the length of the estimation sample, and a put on one asset does not
  depend on other assets. The required results follow the slides'
  calibration; a pre-P0 volatility estimate is at most an optional extension.
- **Added: the look-ahead-bias note.** I asked whether the exercise check
  used future data. The exercise rule itself only compares P_t with the
  boundary at hour t, but s is estimated from the option's own window, as the
  slides specify. I had the README state this limitation.
- **Commit order and clean rerun:** I had the tests committed first
  (`f637204`), then the code (`184680a`), and the results rerun from that
  clean commit. For the timed rerun I paused OneDrive sync and closed
  VS Code to reduce background load.

## What I checked myself

- the slides' tasks against the README: every task (two-period check,
  BTC 1 year with boundary and exercise check, full file, 40 assets for
  1 and 5 years, table of N, assets, seconds and peak memory) has a result
- that only files under `Submissions/BonackerMaurice/Class3/` were committed
- the plausibility of the results, with help from a second AI (Claude chat):
  full-tree memory matches N²/2 × 8 bytes (about 7.2 GiB at N = 43,822,
  18.3 GiB at N = 70,000); the BTC put values (15.2% and 33.7% of the strike)
  are in line with a Black–Scholes estimate; the exercise dates (June 2022,
  June 2026) fall in real market crashes; the payoff 109,608 − 68,019 = 41,589
- that the three versions give the same value and boundary at every N, and
  that the clean rerun reproduces the first run's values exactly

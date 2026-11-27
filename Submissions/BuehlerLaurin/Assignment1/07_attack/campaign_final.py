"""Final-B differential campaign (own/attack), addendum 2026-11-23.
python -B 07_attack/campaign_final.py <seeds> <events> <long_seeds> <long_events>

Same oracle, generator and every-event comparison as campaign.py (result, snapshot,
best bid/ask, last_seq after EVERY event), restricted to the final Version B
(registry key "B" = B3r) and the documented variant B3r_fast. Four modes per stream:
  every   - process(), inspection after every event
  sparse  - process(), inspection only every 97 events (lazy structures cannot clean up)
  direct  - random mix of AddLimitOrder / FillMarketSell / CancelOrder / process,
            including deliberately wrong method-for-type calls
  scramble- callers mutate returned results/snapshots afterwards (aliasing attack)
Planted-bug check first: each mutant of the oracle must be caught by the same fuzzer."""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "01_code"), str(ROOT / "07_attack")]
from campaign_mutants import MUTANTS  # noqa: E402
from fuzz import REGIMES, compare, gen, shrink  # noqa: E402
from lob import METHODS  # noqa: E402

seeds, n, long_seeds, long_n = (int(x) for x in sys.argv[1:5])
TARGETS = {"B": METHODS[("lob", "B")], "B3r_fast": METHODS[("lob", "B3r_fast")]}
print("registry B is B3r class:", METHODS[("lob", "B")] is METHODS[("lob", "B3r")],
      "| B ->", TARGETS["B"].__module__ + "." + TARGETS["B"].__name__,
      "| B3r_fast ->", TARGETS["B3r_fast"].__module__ + "." + TARGETS["B3r_fast"].__name__, flush=True)
MODES = {"every": {}, "sparse": {"inspect": False}, "direct": "direct", "scramble": {"scramble": True}}


def kw_for(mode, s):
    return {"direct_seed": s} if MODES[mode] == "direct" else MODES[mode]


t0 = time.time()
for mut in MUTANTS:
    hit = next(((reg, s) for s in range(30) for reg in REGIMES if compare(mut, gen(s, n, reg))), None)
    print("planted bug", mut.__name__, "found at" if hit else "NOT FOUND", hit, flush=True)
    assert hit, mut.__name__

bad = 0
for v, f in TARGETS.items():
    for label, base, count, size in (("short", 20_000, seeds, n), ("long", 30_000, long_seeds, long_n)):
        for reg in REGIMES:
            ev_total = cmp_total = 0
            for s in range(count):
                ev = gen(base + s, size, reg)
                ev_total += len(ev)
                for mode in MODES:
                    kw = kw_for(mode, base + s)
                    cmp_total += len(ev)
                    d = compare(f, ev, **kw)
                    if d:
                        bad += 1
                        print("BREAK", v, label, reg, base + s, mode, d, flush=True)
                        print("  shrunk:", shrink(f, ev, **kw), flush=True)
                        break
            print(f"{v:8} {label:5} {reg:7} seeds {base}..{base + count - 1} x {size} = {ev_total} events,"
                  f" {len(MODES)} modes = {cmp_total} event comparisons; breaks so far {bad}", flush=True)
print("total breaks", bad, "seconds", round(time.time() - t0))

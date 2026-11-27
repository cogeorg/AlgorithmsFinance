#!/usr/bin/env python3
"""cProfile both versions (separate run; profiler overhead inflates absolute times).

Shows which functions consume the time, i.e. the measured bottleneck that motivated
Version B. Saves the top functions by own time (tottime) to results/profile.json.
"""
import cProfile
import pstats

from _util import RESULTS, VERSIONS, input_path, save_json
from lob.common import read_events

CONFIGS = [("A", "buildup", 10000), ("B", "buildup", 10000), ("A", "mixed", 10000), ("B", "mixed", 10000),
           ("B", "buildup", 100000), ("B", "mixed", 100000)]


def main():
    out = []
    for version, scenario, n in CONFIGS:
        events = read_events(input_path(scenario, n, 42))
        book = VERSIONS[version]()
        prof = cProfile.Profile()
        prof.enable()
        for ev in events:
            book.process(ev)
        prof.disable()
        st = pstats.Stats(prof)
        total = st.total_tt
        rows = []
        for (file, line, func), (cc, nc, tt, ct, _) in st.stats.items():
            rows.append({"function": f"{file.split('/')[-1]}:{line}({func})" if line else func,
                         "calls": nc, "tottime_s": round(tt, 6), "cumtime_s": round(ct, 6),
                         "share_of_total": round(tt / total, 4) if total else None})
        rows.sort(key=lambda r: -r["tottime_s"])
        out.append({"version": version, "scenario": scenario, "events": n, "seed": 42,
                    "total_profiled_s": round(total, 4), "top": rows[:8]})
        print(f"{version} {scenario} {n}: total {total:.3f}s; top: " +
              "; ".join(f"{r['function']} {r['share_of_total']:.0%}" for r in rows[:3]), flush=True)
    save_json(RESULTS / "profile.json", {"note": "cProfile, tottime = time inside the function itself; "
                                                 "profiler overhead inflates absolute times", "runs": out})


if __name__ == "__main__":
    main()

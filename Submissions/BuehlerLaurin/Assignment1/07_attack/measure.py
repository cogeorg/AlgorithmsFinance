"""Attack measurements (own/attack). One fresh subprocess per run, hard 60 s limit each.

    python -B 07_attack/measure.py time <attack> <versions,> <sizes,> [predicted per version,]
    python -B 07_attack/measure.py mem  <kind> <versions,> <arg tuples like 100x200,>
    python -B 07_attack/measure.py lat  <stream> <versions,> <n> [gc|nogc]
    python -B 07_attack/measure.py counts <attack> <version> <n>
    python -B 07_attack/measure.py cell ...          (internal worker)

Timing: 3 repeats per size, median; slope from growth.exponent (log-log least squares).
A cell that hits 60 s (prefill + timed part) is "stopped"; larger sizes are not run.
Memory: tracemalloc in the worker, started before the book is built, events generated lazily
(one at a time) so that the input list is not part of the traced bytes; gc.collect() before
every reading. Order-id strings kept by the engine DO count (they are book state).
"""
import gc
import json
import statistics
import subprocess
import sys
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "01_code"), str(ROOT / "07_attack")]
LIMIT_S = 60.0
CAP = 2 * 1024**3


def make(version, **kw):
    from b3r_model import B3rF, B3rL, B3rT
    from lob import METHODS
    table = {k[1]: f for k, f in METHODS.items()}
    table.update(B3rL=B3rL, B3rF=B3rF, B3rT=B3rT)
    return table[version](**kw)


def cell_time(attack, version, n):
    import gen_attack
    pre, out = gen_attack.TIMED[attack](int(n))
    b = make(version)
    for e in pre:
        b.process(e)
    gc.collect()
    p = b.process
    t0 = time.perf_counter()
    for e in out:
        p(e)
    dt = time.perf_counter() - t0
    return {"s": dt, "events": len(out), "live": len(b.snapshot()),
            "rebuilds": getattr(b, "rebuilds", None),
            "heap": len(b.bids.heap) if hasattr(b.bids, "heap") else None}


def cell_mem(kind, version, args):
    import gen_attack
    a = [int(x) for x in args.split("x")]
    stream = getattr(gen_attack, "mem_" + kind)(*a)
    total = sum(1 for _ in getattr(gen_attack, "mem_" + kind)(*a))
    marks = {max(1, total * k // 10) for k in range(1, 11)}
    make(version)                      # import the engine before tracing starts
    gc.collect()
    tracemalloc.start()
    base = tracemalloc.get_traced_memory()[0]
    b, curve, live_peak = make(version), [], 0
    for i, e in enumerate(stream, 1):
        b.process(e)
        if hasattr(b, "orders"):
            live_peak = max(live_peak, len(b.orders))
        if i in marks:
            e = None
            gc.collect()
            cur = tracemalloc.get_traced_memory()[0] - base
            live = len(b.orders) if hasattr(b, "orders") else len(b.bids) + len(b.asks)
            curve.append([i, live, cur])
            if cur > CAP:
                return {"curve": curve, "status": "stopped: 2 GiB"}
    return {"curve": curve, "live_peak": live_peak,
            "peak": tracemalloc.get_traced_memory()[1] - base}


def cell_lat(stream, version, n, mode="gc"):
    import gen_attack
    ev = getattr(gen_attack, "lat_" + stream)(int(n))
    b = make(version)
    pauses = []
    gc.collect()
    if mode == "nogc":
        gc.disable()
    state = [0]

    def cb(phase, info):
        if phase == "start":
            state[0] = time.perf_counter_ns()
        else:
            pauses.append((time.perf_counter_ns() - state[0], info["generation"]))
    gc.callbacks.append(cb)
    ns, clock, p = [], time.perf_counter_ns, b.process
    for e in ev:
        t = clock()
        p(e)
        ns.append(clock() - t)
    gc.callbacks.remove(cb)
    order = sorted(range(len(ns)), key=ns.__getitem__)
    q = lambda f: ns[order[max(0, -(-len(ns) * f // 1000) - 1)]] / 1000  # noqa: E731  nearest rank
    worst = order[-1]
    return {"n": len(ns), "p50_us": q(500), "p95_us": q(950), "p99_us": q(990), "p999_us": q(999),
            "max_us": ns[worst] / 1000, "max_at": worst, "max_type": ev[worst]["type"],
            "sum_s": sum(ns) / 1e9, "gc_runs": len(pauses),
            "gc_worst_us": max((x for x, _ in pauses), default=0) / 1000,
            "gc_total_ms": sum(x for x, _ in pauses) / 1e6}


def counts(attack, version, n):
    import gen_attack
    pre, out = gen_attack.TIMED[attack](int(n))
    b = make(version, count_operations=True)
    for e in pre + out:
        b.process(e)
    c = b.counters.as_dict()
    print(attack, version, n, "events", len(pre) + len(out), json.dumps(c))


def spawn(*args):
    t0 = time.perf_counter()
    try:
        cp = subprocess.run([sys.executable, "-B", __file__, "cell", *map(str, args)], cwd=ROOT,
                            capture_output=True, text=True, timeout=LIMIT_S)
    except subprocess.TimeoutExpired:
        return {"stopped": True}
    if cp.returncode:
        return {"error": cp.stderr[-1500:], "stopped": True}
    r = json.loads(cp.stdout)
    r["wall"] = time.perf_counter() - t0
    return r


def run_time(attack, versions, sizes, predicted=()):
    from growth import exponent, report
    result = {}
    for v, pred in zip(versions, list(predicted) + [None] * len(versions)):
        rows, stop, last = [], False, {}
        for n in sizes:
            raw = []
            if not stop:
                for _ in range(3):
                    r = spawn("time", attack, v, n)
                    if r.get("stopped"):
                        stop = True
                        if "error" in r:
                            print(r["error"])
                        break
                    raw.append(r["s"])
                    last = r
            rows.append({"n": n, "seconds": statistics.median(raw) if raw else None,
                         "status": "stopped" if stop else "ok", "repeats": len(raw), "raw": raw})
        print(report(rows, pred, f"{attack} {v}"))
        print("  raw:", json.dumps({r["n"]: [round(x, 6) for x in r["raw"]] for r in rows}))
        print("  last cell:", json.dumps({k: last.get(k) for k in ("events", "live", "rebuilds", "heap")}), flush=True)
        result[v] = (rows, exponent(rows))
    return result


def main():
    mode, rest = sys.argv[1], sys.argv[2:]
    if mode == "cell":
        fn = {"time": cell_time, "mem": cell_mem, "lat": cell_lat}[rest[0]]
        print(json.dumps(fn(*rest[1:])))
    elif mode == "time":
        preds = [float(x) if x != "-" else None for x in rest[3].split(",")] if len(rest) > 3 else []
        run_time(rest[0], rest[1].split(","), [int(x) for x in rest[2].split(",")], preds)
    elif mode == "mem":
        for args in rest[2].split(","):
            for v in rest[1].split(","):
                r = spawn("mem", rest[0], v, args)
                print(f"mem {rest[0]} {v} args={args}", json.dumps(r), flush=True)
    elif mode == "lat":
        for v in rest[1].split(","):
            print(f"lat {rest[0]} {v}", json.dumps(spawn("lat", rest[0], v, rest[2], *rest[3:])), flush=True)
    elif mode == "counts":
        counts(*rest)


if __name__ == "__main__":
    main()

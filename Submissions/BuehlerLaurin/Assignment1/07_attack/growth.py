"""Measure how running time grows with input size and fit a growth exponent.

Usage from attack code (copy this file to <exercise>/07_attack/ or import it):

    from growth import measure_growth, report
    rows = measure_growth(build=lambda n: make_stream(n, seed=42),   # outside timing
                          run=lambda stream: replay(Version(), stream),
                          sizes=[1_000, 2_000, 4_000, 8_000, 16_000],
                          repeats=3, limit_s=60)
    print(report(rows, predicted=2.0, label="B1 far-end inserts"))

`build(n)` prepares the input (not timed). `run(state)` is timed with perf_counter;
the median of `repeats` is used. If one run exceeds `limit_s`, larger sizes are
skipped and marked "stopped" (never extrapolated). The exponent is the least-squares
slope of log(seconds) on log(n): 1 ≈ linear, 2 ≈ quadratic. It describes the measured
range only; it is consistent or inconsistent with a claimed bound, it never proves one.
"""
import math
import statistics
import time


def measure_growth(build, run, sizes, repeats=3, limit_s=60.0):
    rows, stopped = [], False
    for n in sizes:
        if stopped:
            rows.append({"n": n, "seconds": None, "status": "stopped", "repeats": 0})
            continue
        times = []
        for _ in range(repeats):
            state = build(n)
            t0 = time.perf_counter()
            run(state)
            dt = time.perf_counter() - t0
            times.append(dt)
            if dt > limit_s:
                stopped = True
                break
        rows.append({"n": n, "seconds": statistics.median(times),
                     "status": "stopped" if stopped else "ok", "repeats": len(times),
                     "raw": times})
    return rows


def exponent(rows):
    pts = [(math.log(r["n"]), math.log(r["seconds"])) for r in rows
           if r["status"] == "ok" and r["seconds"] and r["seconds"] > 0]
    if len(pts) < 3:
        return None
    mx = sum(x for x, _ in pts) / len(pts)
    my = sum(y for _, y in pts) / len(pts)
    sxx = sum((x - mx) ** 2 for x, _ in pts)
    return sum((x - mx) * (y - my) for x, y in pts) / sxx if sxx else None


def report(rows, predicted=None, label="", tol=0.3):
    k = exponent(rows)
    lines = [f"growth: {label}"]
    for r in rows:
        s = "stopped" if r["seconds"] is None else f"{r['seconds']:.6f} s"
        lines.append(f"  n={r['n']:>10}  {s}  ({r['status']}, repeats={r['repeats']})")
    if k is None:
        lines.append("  exponent: not enough completed sizes (need >= 3, ideally >= 4)")
    else:
        lines.append(f"  measured exponent: {k:.2f}")
        if predicted is not None:
            ok = abs(k - predicted) <= tol
            lines.append(f"  predicted: {predicted:.2f} -> {'consistent' if ok else 'INCONSISTENT'} (tol {tol})")
    return "\n".join(lines)


if __name__ == "__main__":
    # Self-check: linear and quadratic toy workloads.
    lin = measure_growth(lambda n: list(range(n)), lambda xs: sum(xs), [20_000, 40_000, 80_000, 160_000])
    quad = measure_growth(lambda n: list(range(n)), lambda xs: [xs.insert(0, 1) for _ in range(len(xs) // 4)],
                          [5_000, 10_000, 20_000, 40_000])
    print(report(lin, predicted=1.0, label="sum (linear)"))
    print(report(quad, predicted=2.0, label="insert at front (quadratic)"))

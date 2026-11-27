import sys, gzip, json, time, glob, cProfile, pstats, io, statistics
sys.path.insert(0, sys.argv[1] + "/01_code")
from lob import METHODS
from lob.validation import validate
files = sorted(glob.glob(sys.argv[1] + "/06_data/supplied/*_10000.jsonl.gz"))
streams = {f.split("/")[-1][:-15]: [json.loads(l) for l in gzip.open(f, "rt")] for f in files}
def t(fn, reps=7):
    xs = []
    for _ in range(reps):
        s = time.perf_counter(); fn(); xs.append(time.perf_counter() - s)
    return statistics.median(xs)
print(f"{'scenario':14s} {'B3r µs/ev':>9s} {'validate':>9s} {'floor':>7s}")
for name, ev in streams.items():
    def full():
        b = METHODS[("lob", "B3r")]()
        for e in ev: b.process(e)
    def val():
        last = 0
        for e in ev:
            validate(e, last, {}.__contains__); last = e["seq"]
    def floor():  # minimum: one call + one result dict per event
        out = None
        for e in ev: out = {"event_id": e["event_id"], "status": "ok"}
    n = len(ev)
    print(f"{name:14s} {t(full)/n*1e6:9.2f} {t(val)/n*1e6:9.2f} {t(floor)/n*1e6:7.2f}")
ev = [e for s in streams.values() for e in s]
pr = cProfile.Profile()
for s in streams.values():
    b = METHODS[("lob", "B3r")](); pr.enable()
    for e in s: b.process(e)
    pr.disable()
out = io.StringIO(); pstats.Stats(pr, stream=out).sort_stats("tottime").print_stats(12); print(out.getvalue()[-2500:])

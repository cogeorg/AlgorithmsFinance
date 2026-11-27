"""Interleaved before/after timing of two version_b.py files.
Usage: ab_timing.py BEFORE.py AFTER.py [scenario ...]   (default: mixed buildup)
Each of BEFORE/AFTER is a path to a version_b-style module; streams: data/generated/<scenario>_100000_s42.jsonl.gz"""
import gc, hashlib, importlib.util, json, statistics, sys, time
sys.path.insert(0, ".")
from lob.common import load_events

def load(path, tag):
    spec = importlib.util.spec_from_file_location(tag, path)
    assert spec is not None and spec.loader is not None
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m.OrderBookB

variants = {"before": load(sys.argv[1], "vb"), "after": load(sys.argv[2], "va")}
REPEATS = 11
for name in (sys.argv[3:] or ["mixed", "buildup"]):
    events = load_events(f"data/generated/{name}_100000_s42.jsonl.gz")
    times = {k: [] for k in variants}; digest = {}
    for rep in range(REPEATS + 1):                      # rep 0 = warm-up
        for tag, cls in (variants.items() if rep % 2 == 0 else reversed(list(variants.items()))):
            book = cls(); proc = book.process
            gc.collect(); gc.disable()
            t = time.perf_counter(); res = [proc(e) for e in events]; dt = time.perf_counter() - t
            gc.enable()
            if rep:
                times[tag].append(dt)
            if rep == 1:
                digest[tag] = hashlib.sha256(json.dumps([res, book.snapshot()]).encode()).hexdigest()[:12]
            del res, book
    b, a = (statistics.median(times[k]) for k in ("before", "after"))
    print(f"{name:8s} before {b:.4f}s  after {a:.4f}s  change {100*(a-b)/b:+.1f}%  "
          f"(min {min(times['before']):.4f} -> {min(times['after']):.4f})  "
          f"same output: {digest['before']==digest['after']}")

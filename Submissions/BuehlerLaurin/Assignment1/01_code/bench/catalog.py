"""Generate all planned inputs OUTSIDE measurement; export commands and hashes."""
import argparse
import gzip
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = Path("06_data/generated/phase4")
MANIFEST = BASE / "manifest.json"
POST_MANIFEST = Path("06_data/generated/post_attack/manifest.json")
SCENARIOS = ("buildup", "crowded", "mixed", "sweep", "cancel_churn")
SIZES = (1000, 10000, 100000)
SEEDS = (42, 43, 44)
GENERATOR_SHA = "ef7f31545addf576e6071cc20a5930f3e2ed93bfef96d4968150fad763d7fe7d"


def plans():
    out = []
    def add(part, workload, size, seed, levels, kind, params=()):
        ident = f"{part}_{workload}_{size}_s{seed}_l{levels}"
        path = BASE / ("official" if kind == "supplied" else "own") / f"{ident}.jsonl.gz"
        if kind == "supplied":
            args = ["06_data/supplied/generate_orders.py", "--scenario", workload,
                    "--events", str(size), "--seed", str(seed), "--levels", str(levels)]
        elif kind == "adversarial":
            args = ["run.py", "datagen.adversarial", "--scenario", workload,
                    "--seed", str(seed), "--levels", str(levels), *params]
        else:
            args = ["run.py", "datagen.benchmark_own", "--kind", workload,
                    "--size", str(size), "--seed", str(seed), "--levels", str(levels)]
        args += ["--out", path.as_posix()]
        out.append({"id": ident, "part": part, "workload": workload, "size": size,
                    "seed": seed, "levels": levels, "own": kind != "supplied",
                    "kind": kind, "path": path.as_posix(), "command": ["python", *args]})
    for size in (*SIZES, 1000000):
        for seed in ((43,) if size == 1000000 else SEEDS):
            for scenario in SCENARIOS:
                add("million" if size == 1000000 else "official", scenario, size, seed, 1000, "supplied")
    for size in SIZES:
        for seed in SEEDS:
            for levels in (4, 1000):
                # levels=1000 reuses the exact official buildup file below.
                add("queue", "buildup", size, seed, levels, "supplied")
            add("liquidation", "liquidation", size, seed, 1000, "own")
            add("adversarial", "deep_book", size, seed, 1000, "adversarial",
                ["--orders", str(size*9//10), "--sells", str(size-size*9//10)])
            add("adversarial", "mid_queue_cancels", size, seed, 4, "adversarial",
                ["--orders", str(size//2), "--cancels", str(size//4)])
            add("adversarial", "repeated_full_sweeps", size, seed, min(1000, size//5-1), "adversarial",
                ["--orders", str(size//5-1), "--rounds", "5"])
            add("churn", "drift", size, seed, 1000, "own")
    add("churn", "drift", 1000000, 43, 1000, "own")
    return out


def file_stats(path):
    digest = hashlib.sha256()
    events = 0
    with gzip.open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
            events += chunk.count(b"\n")
    return {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "content_sha256": digest.hexdigest(), "events": events, "bytes": path.stat().st_size}


def post_attack_plans():
    """Additional filter cases, labelled and separate from the registered grid."""
    from datagen.attack_cases import REGISTRATION, SCENARIOS as ADDED
    entries = []
    for scenario in ADDED:
        memory = scenario in ("rotating_bursts", "pinned_dead")
        sizes = (25, 50, 100, 200) if scenario == "rotating_bursts" else (
            (500, 1000, 2000, 4000) if scenario == "pinned_dead" else SIZES)
        for n in sizes:
            if scenario == "far_end_flicker":
                pre, work = n, 2*n
            elif scenario == "dead_slot_rebuild":
                pre, work = 2*n-1, 2*(n//2)
            elif scenario == "two_side_thrash":
                pre, work = 3*n+3, 2*n
            elif scenario == "spike_purge_at_threshold":
                pre, work = 3*n, 1
            else:
                pre, work = 0, n*(4001 if scenario == "rotating_bursts" else 65)
            path = POST_MANIFEST.parent / f"{scenario}_{n}.jsonl.gz"
            entries.append({"id": f"post_attack_{scenario}_{n}", "part": "post_attack",
                "workload": scenario, "size": work if memory else n, "driver_n": n,
                "events": pre+work, "prefill_events": pre, "query_events": work,
                "levels": n, "seed": 42, "deterministic": True, "own": True,
                "kind": "post_attack", "registration": REGISTRATION,
                "modes": ["memory"] if memory else ["timing", "latency", "memory", "counts"],
                "path": path.as_posix(), "command": ["python", "run.py", "datagen.attack_cases",
                    "--scenario", scenario, "--n", str(n), "--out", path.as_posix()]})
    return entries


def prepare_post_attack():
    """Keep registered data/manifest unchanged; export a new combined catalog."""
    catalog = load()
    source = Path("01_code/datagen/attack_cases.py")
    added = post_attack_plans()
    for entry in added:
        path = Path(entry["path"])
        if not path.exists():
            subprocess.run([sys.executable, *entry["command"][1:]], check=True, capture_output=True, text=True)
        stats = file_stats(path)
        assert stats["events"] == entry["events"], entry["id"]
        metadata = json.loads(path.with_suffix(path.suffix+".metadata.json").read_text(encoding="utf-8"))
        assert metadata["prefill_events"] == entry["prefill_events"] and metadata["sha256"] == stats["sha256"]
        entry.update(stats, generator_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        catalog["entries"].append(entry)
        print(entry["id"], entry["sha256"], flush=True)
    previous = json.loads(POST_MANIFEST.read_text(encoding="utf-8")) if POST_MANIFEST.exists() else {}
    # Verification of identical inputs must not dirty a committed source tree.
    catalog["post_attack_created_utc"] = (
        previous["post_attack_created_utc"] if previous.get("entries") == catalog["entries"]
        else datetime.now(timezone.utc).isoformat())
    catalog["physical_files"] = len({e["path"] for e in catalog["entries"]})
    catalog["physical_compressed_bytes"] = sum(e["bytes"] for e in {e["path"]: e for e in catalog["entries"]}.values())
    data = json.dumps(catalog, indent=2)+"\n"
    POST_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    POST_MANIFEST.write_text(data, encoding="utf-8")
    (ROOT/"00_docs/POST_ATTACK_MANIFEST.json").write_text(data, encoding="utf-8")
    print(f"RESULT: PASS ({len(added)} added cases generated/hash-verified outside timing; original manifest unchanged)")


def prepare():
    source = ROOT / "06_data/supplied/generate_orders.py"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == GENERATOR_SHA
    started = time.perf_counter()
    catalog = {"created_utc": datetime.now(timezone.utc).isoformat(),
               "supplied_generator_sha256": GENERATOR_SHA, "data_only_not_measurement": True, "entries": []}
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    for entry in plans():
        path = ROOT / entry["path"]
        if entry["part"] == "queue" and entry["levels"] == 1000:
            original = next(e for e in catalog["entries"] if e["part"] == "official" and
                            e["workload"] == "buildup" and e["size"] == entry["size"] and e["seed"] == entry["seed"])
            entry.update({k: original[k] for k in ("path", "command", "sha256", "content_sha256", "events", "bytes")})
            entry["reuses"] = original["id"]
            entry["generation_s"] = 0.0
        else:
            t0 = time.perf_counter()
            if not path.exists():
                subprocess.run([sys.executable, *entry["command"][1:]], cwd=ROOT,
                               check=True, capture_output=True, text=True)
            entry.update(file_stats(path))
            assert entry["events"] == entry["size"], entry
            meta = json.loads(path.with_suffix(path.suffix + ".metadata.json").read_text(encoding="utf-8"))
            assert meta["sha256"] == entry["sha256"], entry["id"]
            entry["generation_s"] = time.perf_counter() - t0
        catalog["entries"].append(entry)
        catalog["generation_wall_s"] = time.perf_counter() - started
        MANIFEST.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
        print(f"{len(catalog['entries']):3d}: {entry['id']} sha256={entry['sha256']}", flush=True)
    # This small manifest is reviewable/committable; the referenced inputs stay ignored.
    verify_and_export(catalog, verify_files=False)
    print(f"RESULT: PASS ({len(catalog['entries'])} data entries; generated outside measurement; {catalog['generation_wall_s']:.1f}s)")


def load(path=MANIFEST):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def verify_and_export(catalog=None, verify_files=True):
    catalog = load() if catalog is None else catalog
    seen = {}
    generators = {"supplied": Path("06_data/supplied/generate_orders.py"),
                  "adversarial": Path("01_code/datagen/adversarial.py"),
                  "own": Path("01_code/datagen/benchmark_own.py")}
    for entry in catalog["entries"]:
        generator = generators[entry["kind"]]
        entry["generator_sha256"] = hashlib.sha256(generator.read_bytes()).hexdigest()
        if entry["kind"] == "supplied":
            assert entry["generator_sha256"] == GENERATOR_SHA
        if verify_files:
            if entry["path"] not in seen:
                seen[entry["path"]] = file_stats(Path(entry["path"]))
            assert all(entry[key] == value for key, value in seen[entry["path"]].items()), entry["id"]
    assert len(catalog["entries"]) == 114
    catalog["python"] = sys.version.split()[0]
    catalog["verified_utc"] = datetime.now(timezone.utc).isoformat()
    catalog["physical_files"] = len({e["path"] for e in catalog["entries"]})
    catalog["physical_compressed_bytes"] = sum(e["bytes"] for e in {e["path"]: e for e in catalog["entries"]}.values())
    text = json.dumps(catalog, indent=2) + "\n"
    MANIFEST.write_text(text, encoding="utf-8")
    (ROOT/"00_docs/DATA_MANIFEST.json").write_text(text, encoding="utf-8")
    return catalog


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--post-attack", action="store_true", help="generate/verify additions and a new combined manifest")
    args = parser.parse_args()
    if args.post_attack:
        prepare_post_attack()
    elif args.verify:
        result = verify_and_export()
        print(f"RESULT: PASS ({len(result['entries'])} manifest entries / {result['physical_files']} physical files verified)")
    else:
        prepare()

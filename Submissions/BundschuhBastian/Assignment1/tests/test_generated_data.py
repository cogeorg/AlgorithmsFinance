"""Phase 5: the committed checksum record of the benchmark streams must stay reproducible.

results/generated_data_checksums.json lists every stream made by bench/make_data.sh. These
tests regenerate the small ones in memory (no files needed) and compare the sha256 of the
decompressed JSON Lines. The big files (100,000 and 1,000,000 events) are checked by
`python tools/hash_generated.py --check` after bench/make_data.sh.
"""
import gzip
import hashlib
import json
from pathlib import Path

import pytest

import generate_orders

ROOT = Path(__file__).resolve().parent.parent
RECORD = json.loads((ROOT / "results" / "generated_data_checksums.json").read_text())["files"]
SCENARIOS = ("buildup", "crowded", "mixed", "sweep", "cancel_churn")


def decompressed_sha(scenario, events, seed, levels):
    """Same bytes that generate_orders.write_stream compresses (one JSON object per line)."""
    digest = hashlib.sha256()
    for row in generate_orders.events(scenario, events, seed, levels):
        digest.update((json.dumps(row, separators=(",", ":")) + "\n").encode())
    return digest.hexdigest()


def expected_names():
    names = {f"{s}_{m}_s{seed}.jsonl.gz" for s in SCENARIOS for m in (1000, 10000, 100000)
             for seed in (42, 43, 44)}
    names |= {f"{s}_1000000_s42.jsonl.gz" for s in SCENARIOS}
    names |= {f"buildup_100000_s42_L{n}.jsonl.gz" for n in (4, 16, 64, 256, 4000)}
    return names


def test_record_lists_exactly_the_planned_streams():
    assert set(RECORD) == expected_names()
    for name, info in RECORD.items():
        assert len(info["decompressed_sha256"]) == 64 and len(info["gz_sha256"]) == 64
        assert info["command"].startswith("python generate_orders.py --scenario ")
        assert f"--events {info['events']} " in info["command"] + " "


def test_record_settings_match_file_names():
    for name, info in RECORD.items():
        stem = name.removesuffix(".jsonl.gz").split("_")
        assert info["seed"] == int(next(p for p in stem if p.startswith("s") and p[1:].isdigit())[1:])
        assert info["levels"] == (int(stem[-1][1:]) if stem[-1].startswith("L") else 1000)


@pytest.mark.parametrize("name", sorted(n for n, i in RECORD.items() if i["events"] <= 10000))
def test_small_streams_regenerate_to_the_recorded_hash(name):
    info = RECORD[name]
    assert decompressed_sha(info["scenario"], info["events"], info["seed"],
                            info["levels"]) == info["decompressed_sha256"]


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_seed_42_10000_equals_the_supplied_file(scenario):
    supplied = ROOT / "data" / f"{scenario}_10000.jsonl.gz"
    plain = hashlib.sha256(gzip.decompress(supplied.read_bytes())).hexdigest()
    assert RECORD[f"{scenario}_10000_s42.jsonl.gz"]["decompressed_sha256"] == plain


def test_crowded_is_buildup_with_four_levels():
    """Queue-concentration runs can use `buildup --levels 4` as the 4-price case."""
    assert (RECORD["crowded_100000_s42.jsonl.gz"]["decompressed_sha256"]
            == RECORD["buildup_100000_s42_L4.jsonl.gz"]["decompressed_sha256"])
    assert decompressed_sha("crowded", 2000, 7, 1000) == decompressed_sha("buildup", 2000, 7, 4)


def test_seeds_give_different_streams():
    for scenario in SCENARIOS:
        hashes = {RECORD[f"{scenario}_1000_s{seed}.jsonl.gz"]["decompressed_sha256"]
                  for seed in (42, 43, 44)}
        assert len(hashes) == 3, scenario

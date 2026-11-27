"""Reading event files (JSON Lines, optionally gzip-compressed).

Reading and parsing are kept separate from the matching engine, so that benchmarks can
report input cost and engine cost separately (assignment README, "Time and latency").
"""
import gzip
import json
from pathlib import Path


def _open(path):
    path = Path(path)
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("r", encoding="utf-8")


def iter_events(path):
    """Stream events one by one (constant memory for the input)."""
    with _open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def read_events(path):
    """Read the whole file into a list of event dictionaries (preloaded input)."""
    return list(iter_events(path))

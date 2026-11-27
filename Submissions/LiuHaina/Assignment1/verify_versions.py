"""Compare results and canonical books after EVERY event; not a benchmark."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
from lob.version_a import OrderBook as VersionA
from lob.version_b import OrderBook as VersionB


def verify(path):
    a, b = VersionA(), VersionB()
    count = rejected = fills = peak = 0
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            event = json.loads(line)
            left, right = a.process_event(event), b.process_event(event)
            if left != right:
                raise AssertionError(f"{path.name}:{line_number}: event results differ")
            orders = a.inspect_book()
            if orders != b.inspect_book() or a.last_seq != b.last_seq:
                raise AssertionError(f"{path.name}:{line_number}: book/sequence differs")
            count += 1
            rejected += left["status"] == "rejected"
            fills += len(left.get("fills", []))
            peak = max(peak, len(orders))
    return dict(file=path.name, input_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                events=count, rejected_events=rejected, fills=fills,
                peak_active_orders=peak, remaining_orders=len(a.inspect_book()),
                last_seq=a.last_seq, every_event_equal=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    results = []
    for path in args.paths:
        result = verify(path)
        results.append(result)
        print(json.dumps(result), flush=True)
    root = Path(__file__).resolve().parent
    hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
              for name in ("lob/version_a.py", "lob/version_b.py", "tests/test_orderbook.py")}
    args.out.write_text(json.dumps(dict(kind="correctness, not performance",
        code_sha256=hashes, files=results), indent=2) + "\n")


if __name__ == "__main__":
    main()

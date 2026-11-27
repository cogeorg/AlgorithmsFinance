"""Replay a teaching JSONL stream and print the final result and canonical book."""
import argparse
import importlib
import json
from orderbook.io import read_events


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path")
    parser.add_argument("--version", choices=("baseline", "revised"), default="revised")
    args = parser.parse_args()
    book = importlib.import_module(f"orderbook.{args.version}").OrderBook()
    last, count, rejected = None, 0, 0
    for event in read_events(args.path):
        last = book.process(event)
        count += 1
        rejected += last["status"] == "rejected"
    print(json.dumps(dict(events=count, rejected=rejected, last_result=last,
                          remaining_orders=book.inspect()), indent=2))


if __name__ == "__main__":
    main()

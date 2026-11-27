"""Replay JSONL or gzipped JSONL; emit event results and final canonical book."""
import argparse
import gzip
import json
from orderbook import BaselineBook, RevisedBook


def load(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input')
    parser.add_argument('--version', choices=['A', 'B'], default='B')
    args = parser.parse_args()
    book = (BaselineBook if args.version == 'A' else RevisedBook)()
    result = None
    for event in load(args.input):
        result = book.process(event)
        print(json.dumps(result))
    print(json.dumps(dict(last_result=result, remaining_orders=book.inspect())))


if __name__ == '__main__':
    main()

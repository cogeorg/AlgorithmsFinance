"""Replay JSON Lines or gzip JSON Lines through either order-book version."""
import argparse
import contextlib
import gzip
import json
import sys
from pathlib import Path

from order_book_v1 import OrderBook as BookA
from order_book_v2 import OrderBook as BookB


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', choices=('A', 'B'), required=True)
    parser.add_argument('--input', type=Path, required=True, help='input .jsonl or .jsonl.gz')
    parser.add_argument('--output', type=Path, help='optional new JSONL output file; existing files are not overwritten')
    args = parser.parse_args()
    if not (args.input.name.endswith('.jsonl') or args.input.name.endswith('.jsonl.gz')):
        parser.error('input must end in .jsonl or .jsonl.gz')
    book = BookA() if args.version == 'A' else BookB()
    processed = rejected = 0
    try:
        with contextlib.ExitStack() as stack:
            opener = gzip.open if args.input.name.endswith('.gz') else open
            source = stack.enter_context(opener(args.input, 'rt', encoding='utf-8'))
            saved = stack.enter_context(args.output.open('x', encoding='utf-8', newline='\n')) if args.output else None

            def emit(record):
                text = json.dumps(record, ensure_ascii=True)
                print(text)
                if saved is not None:
                    saved.write(text + '\n')

            for line_number, line in enumerate(source, 1):
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as exc:
                    result = {'status': 'rejected', 'reason': f'malformed JSON: {exc.msg}'}
                else:
                    result = book.process_event(event)
                processed += 1
                rejected += result.get('status') == 'rejected'
                emit({'record': 'event', 'line': line_number, 'result': result})
            emit({'record': 'final_book', 'version': args.version, 'events': processed,
                  'rejected': rejected, 'orders': book.inspect_book()})
    except (OSError, UnicodeError, EOFError) as exc:
        print(f'Replay error: {exc}', file=sys.stderr)
        return 2
    return 1 if rejected else 0


if __name__ == '__main__':
    sys.exit(main())

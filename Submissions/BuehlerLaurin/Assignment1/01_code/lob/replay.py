"""Replay JSON Lines (plain or gzip) in file order from a fresh book.

Usage: python run.py lob.replay <file.jsonl[.gz]> [--version A|B|B1|B2|B3|B3r|B3r_fast]
Default B is the final Version B (B3r); use --version A for the baseline.
B1 explicitly selects the original variant.
No sorting: seq order is validated by the engine, and rejections stay in place.
"""
import argparse
import gzip
import json
import re
import sys
from pathlib import Path

from lob import METHODS

_BAD_UTF8 = re.compile('[\udc80-\udcff]')


class ReplayInputError(ValueError):
    """A physical input line could not be read as UTF-8 JSON Lines."""
    def __init__(self, path, line, problem):
        self.path, self.line, self.problem = path, line, problem
        super().__init__(problem)

    def __str__(self):
        # Keep the diagnostic a single line even for unusual filenames/errors.
        message = f'{self.path}:{self.line}: {self.problem}'
        return message.replace('\r','\\r').replace('\n','\\n')


def read_events(path):
    """Stream parsed events without retaining the input file or result history."""
    path = Path(path)
    # SPEC has no integer upper bound. The standard JSON decoder AND encoder
    # use CPython's process-wide decimal conversion guard; permit arbitrary
    # lengths in this replay process, including the returned residual quantity.
    if hasattr(sys, "set_int_max_str_digits"):
        sys.set_int_max_str_digits(0)
    opener = gzip.open if path.suffix == ".gz" else open
    number = 0
    try:
        # Surrogateescape defers invalid-byte reporting to its physical line,
        # rather than failing on TextIO's read-ahead before earlier valid lines.
        # Text mode retains CRLF/bare-CR universal-newline behaviour.
        with opener(path, "rt", encoding="utf-8-sig", errors="surrogateescape") as stream:
            for number,line in enumerate(stream,1):
                if number == 1 and line.startswith(('\udcff\udcfe','\udcfe\udcff')):
                    raise ReplayInputError(path,number,'UTF-16 input is not supported; use UTF-8')
                if _BAD_UTF8.search(line):
                    raise ReplayInputError(path,number,'invalid UTF-8 input')
                if '\x00' in line:
                    raise ReplayInputError(path,number,'NUL byte in input; use UTF-8 JSON Lines, not UTF-16')
                if line.lstrip().startswith('\ufeff'):
                    raise ReplayInputError(path,number,'unexpected BOM; only one leading UTF-8 BOM is allowed')
                if line.strip():
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise ReplayInputError(path,number,f'invalid JSON: {exc.msg}') from None
                    yield event
    except (OSError,EOFError) as exc:
        raise ReplayInputError(path,max(1,number+1),str(exc)) from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    versions = tuple(key[1] for key in sorted(METHODS))
    parser.add_argument("--version", choices=versions, default="B",
                        help="implementation (default: %(default)s = B3r, final Version B; A is the baseline)")
    args = parser.parse_args()
    book = METHODS[("lob", args.version)]()
    try:
        for event in read_events(args.path):
            print(json.dumps(book.process(event)))
    except ReplayInputError as exc:
        print(str(exc),file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

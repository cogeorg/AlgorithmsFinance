"""Sequential JSONL and gzipped-JSONL replay entry point."""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path
from typing import Any, TextIO

from .baseline import BaselineOrderBook
from .optimized import OptimizedOrderBook


def _open_text(path: Path) -> TextIO:
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("rt", encoding="utf-8")


def replay_file(path: str | Path, engine: Any) -> list[dict[str, Any]]:
    """Replay a file sequentially and return one public result per line."""

    resolved = Path(path).resolve()
    results: list[dict[str, Any]] = []
    with _open_text(resolved) as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                raise ValueError(f"{resolved}: line {line_number}: blank JSONL line")
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{resolved}: line {line_number}: malformed JSON: {exc.msg}"
                ) from exc
            results.append(engine.process_event(event))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="JSONL or .jsonl.gz file to replay")
    parser.add_argument("--engine", choices=("baseline", "optimized"), required=True)
    args = parser.parse_args(argv)

    engine = BaselineOrderBook() if args.engine == "baseline" else OptimizedOrderBook()
    resolved = Path(args.path).resolve()
    print(f"Replaying {resolved} with {args.engine}", file=sys.stderr)
    for result in replay_file(resolved, engine):
        print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


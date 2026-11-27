#!/usr/bin/env python3
"""Mutation check: can the unchanged tests fail for the mistakes that matter?

Each mutation injects ONE deliberate bug into a temporary copy of lob/ (tests/ and the small
data samples are copied unchanged) and runs tests.test_spec + tests.test_equivalence there.
A mutation is "detected" when the test run fails. The repository itself is never modified.
The unmutated copy is run first and must pass. Results: results/mutations.json.
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from _util import RESULTS, ROOT, save_json

# (name, file, exact original snippet (must occur exactly once), replacement)
MUTATIONS = [
    # --- engine and shared code ---------------------------------------------------------
    ("A: LIFO instead of FIFO at equal price", "lob/book_a.py",
     "o.price > best_p", "o.price >= best_p"),
    ("B: partially filled maker loses its queue position", "lob/book_b.py",
     "maker[0] = mq - qty", "maker[0] = mq - qty; level.move_to_end(maker_id)"),
    ("B: limit order trades at the taker's limit instead of the resting price", "lob/book_b.py",
     '"price_ticks": price, "qty_units": mq}', '"price_ticks": (price if min_key is None else sign * min_key), "qty_units": mq}'),
    ("shared: JSON true accepted as an integer", "lob/common.py",
     "return type(x) is int and x > 0", "return isinstance(x, int) and x > 0"),
    ("B (generic cancel): empty price level kept", "lob/book_b.py",
     "        if not level:\n            self._remove_level(levels, keys, price, key)\n        return order[QTY]",
     "        if False:\n            self._remove_level(levels, keys, price, key)\n        return order[QTY]"),
    ("shared: rejected event advances the last accepted seq", "lob/common.py",
     "        if reason is not None:\n            return self._rejected(event, reason)",
     "        if reason is not None:\n            if isinstance(event, dict) and type(event.get('seq')) is int:\n"
     "                self.last_seq = max(self.last_seq, event['seq'])\n            return self._rejected(event, reason)"),
    ("A: market-sell residual rests in the book", "lob/book_a.py",
     "return self._match(order_id, SELL, qty, None)",
     "fills, rest = self._match(order_id, SELL, qty, None); rest and self.asks.append("
     "Order(order_id, SELL, 10**9, rest, self.last_seq + 1)); return fills, rest"),
    ("B: an equal price does not cross", "lob/book_b.py",
     "if min_key is not None and key < min_key:", "if min_key is not None and key <= min_key:"),
    # --- Version B fast path --------------------------------------------------------------
    ("fast path: LIMIT accepts bool price/qty", "lob/book_b.py",
     "type(price) is not int or price <= 0\n                    or type(qty) is not int",
     "not isinstance(price, int) or price <= 0\n                    or not isinstance(qty, int)"),
    ("fast path: LIMIT skips the duplicate-live-id check", "lob/book_b.py",
     "                    or type(qty) is not int or qty <= 0 or oid in self.index):",
     "                    or type(qty) is not int or qty <= 0):"),
    ("fast path: BUY at the best ask does not cross", "lob/book_b.py",
     "if keys and -keys[-1] <= price:", "if keys and -keys[-1] < price:"),
    ("fast path: SELL at the best bid does not cross", "lob/book_b.py",
     "if keys and keys[-1] >= price:", "if keys and keys[-1] > price:"),
    ("fast path: cancel keeps an empty price level", "lob/book_b.py",
     "            if not level:\n                self._remove_level(levels, keys, price, key)\n            return {",
     "            if False:\n                self._remove_level(levels, keys, price, key)\n            return {"),
    ("fast path: cancel does not advance seq", "lob/book_b.py",
     "            order = self.index.pop(target, None)\n            self.last_seq = seq",
     "            order = self.index.pop(target, None)"),
    ("fast path: market-sell status partial/unfilled swapped", "lob/book_b.py",
     '("partial" if fills else "unfilled")', '("unfilled" if fills else "partial")'),
    ("fast path: MARKET_SELL skips the duplicate-live-id check", "lob/book_b.py",
     "if type(oid) is not str or not oid or type(qty) is not int or qty <= 0 or oid in self.index:",
     "if type(oid) is not str or not oid or type(qty) is not int or qty <= 0:"),
    ("fast path: accepts an equal (nonincreasing) seq", "lob/book_b.py",
     "or seq <= self.last_seq or", "or seq < self.last_seq or"),
    ("fast path: wrong arrival seq stored for a resting BUY", "lob/book_b.py",
     "order = [qty, BUY, price, seq]", "order = [qty, BUY, price, seq + 1]"),
    ("fast path: cancel accepts a non-string target", "lob/book_b.py",
     "if type(target) is not str or not target:", "if not target:"),
    ("fast path: resting SELL stored on the bid side", "lob/book_b.py",
     "level = self._add_level(self.ask_levels, self.ask_keys, price, -price)",
     "level = self._add_level(self.bid_levels, self.bid_keys, price, price)"),
]

TESTS = ["tests.test_spec", "tests.test_equivalence"]


def run_tests(copy_dir):
    r = subprocess.run([sys.executable, "-m", "unittest", *TESTS], cwd=copy_dir, capture_output=True, text=True)
    summary = next((line for line in reversed(r.stderr.splitlines()) if line.startswith(("OK", "FAILED"))), "")
    failing = sum(int(n) for n in re.findall(r"(?:failures|errors)=(\d+)", summary))
    return r.returncode, summary, failing


def make_copy(dst):
    for sub in ("lob", "tests", "data"):
        shutil.copytree(ROOT / sub, dst / sub, ignore=shutil.ignore_patterns("generated", "__pycache__"))


def main():
    with tempfile.TemporaryDirectory() as d:
        make_copy(Path(d))
        code, summary, _ = run_tests(d)
    baseline_ok = code == 0
    print(f"unmutated copy: {summary}", flush=True)
    if not baseline_ok:
        raise SystemExit("the unmutated copy must pass before mutations mean anything")
    results = []
    for name, rel, old, new in MUTATIONS:
        with tempfile.TemporaryDirectory() as d:
            make_copy(Path(d))
            f = Path(d) / rel
            src = f.read_text()
            if src.count(old) != 1:
                raise SystemExit(f"mutation {name!r}: snippet occurs {src.count(old)} times in {rel}")
            f.write_text(src.replace(old, new))
            code, summary, failing = run_tests(d)
        results.append({"name": name, "file": rel, "detected": code != 0, "failures": failing, "summary": summary})
        print(f"{'detected' if code else 'MISSED  '}  {name}  ({summary})", flush=True)
    save_json(RESULTS / "mutations.json", {"tests": TESTS, "baseline_passes": baseline_ok, "mutations": results})
    print(f"{sum(r['detected'] for r in results)} of {len(results)} mutations detected")


if __name__ == "__main__":
    main()

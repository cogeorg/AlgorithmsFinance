"""Replay CLI probes for the final Version B (own/attack), addendum 2026-11-23.
python -B 07_attack/cli_probe_final.py
Versions: B (registry alias of B3r), B3r, B3r_fast. Temp files only.
For files that SPEC D3 says must be accepted (BOM, plain and gzip; integers of any length)
every printed result line is compared with oracle.py run on the same events (parsed here
with CPython's digit guard disabled). Files outside the spec (UTF-16, malformed JSON, ...)
are probed for behaviour only; the SPEC sets no rule for them."""
import gzip
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "07_attack"))
from oracle import Oracle  # noqa: E402

sys.set_int_max_str_digits(0)
BIG = lambda d: "9" * d  # noqa: E731


def L(seq, oid, side, p, q):
    return (f'{{"seq": {seq}, "event_id": "e{seq}", "type": "LIMIT", "order_id": "{oid}", '
            f'"side": "{side}", "price_ticks": {p}, "qty_units": {q}}}')


def S(seq, q):
    return f'{{"seq": {seq}, "event_id": "e{seq}", "type": "MARKET_SELL", "order_id": "m{seq}", "qty_units": {q}}}'


def C(seq, t):
    return f'{{"seq": {seq}, "event_id": "e{seq}", "type": "CANCEL", "target_order_id": "{t}"}}'


def lines(*xs):
    return ("\n".join(xs) + "\n").encode()


BOM = b"\xef\xbb\xbf"
base = lines(L(1, "b1", "BUY", 5, 3), L(2, "s1", "SELL", 5, 1), S(3, 1), C(4, "b1"), C(5, "b1"))
SPEC_CASES = {  # name -> (bytes, gzip?)
    "control": (base, False),
    "control gz": (base, True),
    "UTF-8 BOM plain": (BOM + base, False),
    "UTF-8 BOM gz": (BOM + base, True),
    "BOM + CRLF": (BOM + base.replace(b"\n", b"\r\n"), False),
    "qty 4301 digits": (lines(L(1, "b1", "BUY", 5, 1), L(2, "b2", "BUY", 5, BIG(4301)), L(3, "b3", "BUY", 5, 1)), False),
    "qty 100k digits, crossed and partly filled": (
        lines(L(1, "b1", "BUY", 7, BIG(100_000)), S(2, BIG(50_000)), L(3, "s1", "SELL", 7, BIG(99_999)),
              C(4, "b1")), False),
    "qty 1M digits": (lines(L(1, "b1", "BUY", 5, BIG(1_000_000)), S(2, 1)), False),
    "price 100k digits both sides": (
        lines(L(1, "b1", "BUY", BIG(100_000), 2), L(2, "s1", "SELL", BIG(100_000), 1),
              L(3, "s2", "SELL", "1" + "0" * 99_999, 1)), False),
    "seq 100k digits then smaller (nonincreasing)": (
        lines(L(int(BIG(100_000)), "b1", "BUY", 5, 1), L(2, "b2", "BUY", 5, 1),
              L("1" + "0" * 100_000, "b3", "BUY", 5, 1)), False),
    "negative 5000-digit qty (bad_qty)": (lines(L(1, "b1", "BUY", 5, "-" + BIG(5000)), L(2, "b2", "BUY", 5, 1)), False),
    "BOM + huge ints gz": (BOM + lines(L(1, "b1", "BUY", BIG(6000), BIG(6000)), S(2, BIG(7000))), True),
}
OTHER_CASES = {
    "UTF-16 file": base.decode().encode("utf-16"),
    "double BOM": BOM + BOM + base,
    "BOM in the middle of the file": base + BOM + lines(L(9, "x", "BUY", 5, 1)),
    "malformed JSON line in the middle": lines(L(1, "b1", "BUY", 5, 1), "{bad", L(3, "b3", "BUY", 5, 1)),
    "invalid UTF-8 byte": lines(L(1, "b1", "BUY", 5, 1)) + b'{"seq": 2, "event_id": "\xff"}\n',
    "empty file": b"",
    "BOM only": BOM,
}


def expected(raw):
    text = raw.decode("utf-8-sig")
    o = Oracle()
    return [o.process(json.loads(x)) for x in text.splitlines() if x.strip()]


def run(raw, gz, version, extra=()):
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / ("x.jsonl.gz" if gz else "x.jsonl")
        f.write_bytes(gzip.compress(raw) if gz else raw)
        return subprocess.run([sys.executable, "-B", "run.py", "lob.replay", str(f), "--version", version, *extra],
                              cwd=ROOT, capture_output=True, timeout=120)


def last_err(p):
    return (p.stderr.decode("utf-8", "replace").strip().splitlines() or [""])[-1][:150]


breaks = 0
for name, (raw, gz) in SPEC_CASES.items():
    want = expected(raw)
    outs = {}
    for v in ("B", "B3r", "B3r_fast"):
        p = run(raw, gz, v)
        outs[v] = p.stdout
        try:
            got = [json.loads(x) for x in p.stdout.decode("utf-8").splitlines()]
        except Exception as ex:  # noqa: BLE001
            got = f"unparseable stdout: {ex!r}"
        ok = p.returncode == 0 and got == want
        breaks += not ok
        print(f"{'OK   ' if ok else 'BREAK'} {v:8} | {name} | exit {p.returncode} | {len(want)} expected,"
              f" {len(got) if isinstance(got, list) else got} printed, statuses"
              f" {[g.get('status') for g in got] if isinstance(got, list) else '-'} | {last_err(p)}", flush=True)
    same = outs["B"] == outs["B3r"]
    breaks += not same
    print(f"{'OK   ' if same else 'BREAK'} B == B3r byte-identical stdout | {name}", flush=True)

for name, raw in OTHER_CASES.items():
    for v in ("B", "B3r_fast"):
        p = run(raw, False, v)
        st = [json.loads(x).get("status") for x in p.stdout.decode("utf-8", "replace").splitlines()]
        print(f"INFO  {v:8} | {name} | exit {p.returncode} | results {st} | {last_err(p)}", flush=True)

for args in (["--version", "b"], ["--version", "B4"], []):
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "x.jsonl"
        f.write_bytes(base)
        cmd = [sys.executable, "-B", "run.py", "lob.replay", str(f), *args]
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, timeout=60)
    print(f"INFO  args {args} | exit {p.returncode} | {len(p.stdout.splitlines())} lines | {last_err(p)}", flush=True)
print("total spec-case breaks", breaks)

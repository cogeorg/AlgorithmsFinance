"""Replay CLI probes (own/attack): odd but plausible input files. Temp files only."""
import json, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def L(seq, q): return json.dumps({"seq": seq, "event_id": f"e{seq}", "type": "LIMIT", "order_id": f"o{seq}", "side": "BUY", "price_ticks": 5, "qty_units": 1}).replace('"qty_units": 1', '"qty_units": ' + q)
ok1, ok3 = L(1, "1"), L(3, "1")
CASES = {
    "control": f"{ok1}\n{ok3}\n".encode(),
    "qty with 4300 digits": f"{ok1}\n{L(2, '9' * 4300)}\n{ok3}\n".encode(),
    "qty with 4301 digits": f"{ok1}\n{L(2, '9' * 4301)}\n{ok3}\n".encode(),
    "UTF-8 BOM (Windows PowerShell Out-File)": b"\xef\xbb\xbf" + f"{ok1}\n{ok3}\n".encode(),
    "UTF-16 file": f"{ok1}\n{ok3}\n".encode("utf-16"),
    "malformed JSON line in the middle": f"{ok1}\n{{bad\n{ok3}\n".encode(),
    "truncated last line": f"{ok1}\n{ok3[:-5]}".encode(),
    "deeply nested unused field": f'{ok1}\n{L(2, "1")[:-1]}, "x": {"[" * 100000}{"]" * 100000}}}\n{ok3}\n'.encode(),
    "invalid UTF-8 byte": f"{ok1}\n".encode() + b'{"seq": 2, "event_id": "\xff"}\n' + f"{ok3}\n".encode(),
    "NaN quantity": f"{ok1}\n{L(2, 'NaN')}\n{ok3}\n".encode(),
    "1e0 quantity": f"{ok1}\n{L(2, '1e0')}\n{ok3}\n".encode(),
    "duplicate key qty": f'{ok1}\n{L(2, "1")[:-1]}, "qty_units": 7}}\n{ok3}\n'.encode(),
}
for v in ("A", "B1", "B2", "B3"):
    for name, raw in CASES.items():
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "x.jsonl"
            f.write_bytes(raw)
            p = subprocess.run([sys.executable, "-B", "run.py", "lob.replay", str(f), "--version", v], cwd=ROOT,
                               capture_output=True, text=True, encoding="utf-8", timeout=60)
        out = [json.loads(x).get("status") for x in p.stdout.splitlines()] if name != "qty with 4301 digits" else len(p.stdout.splitlines())
        print(v, "|", name, "| exit", p.returncode, "| results", out, "|", (p.stderr.strip().splitlines() or [""])[-1][:140])

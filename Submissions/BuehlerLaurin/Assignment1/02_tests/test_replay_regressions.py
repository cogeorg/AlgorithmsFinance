"""ATK-01/BOM regressions: test the real CLI, including huge integer output."""
import gzip
import json
import subprocess
import sys

import pytest
from lob import METHODS


@pytest.mark.parametrize("version", [key[1] for key in sorted(METHODS)])
@pytest.mark.parametrize("compressed", [False, True])
@pytest.mark.parametrize("huge", [False, True], ids=["utf8-bom", "atk01-int-5000-digits"])
def test_regression_replay_bom_and_unbounded_integer(tmp_path, version, compressed, huge):
    digits = "9" * 5000 if huge else "7"
    # Build JSON literals directly, independently of this process's int guard.
    events = []
    for seq in range(1, 4):
        events.append('{"seq":'+str(seq)+',"event_id":"e'+str(seq)+'","type":"LIMIT",'
                      '"order_id":"o'+str(seq)+'","side":"BUY","price_ticks":1,"qty_units":'+digits+'}')
    payload = ("\n".join(events)+"\n").encode()
    if not huge:
        payload = b"\xef\xbb\xbf" + payload
    path = tmp_path/("events.jsonl.gz" if compressed else "events.jsonl")
    path.write_bytes(gzip.compress(payload) if compressed else payload)
    result = subprocess.run([sys.executable, "-X", "int_max_str_digits=4300", "run.py", "lob.replay",
                             str(path), "--version", version], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    got = [json.loads(line, parse_int=str) for line in result.stdout.splitlines()]
    assert len(got) == 3
    assert [r["order_id"] for r in got] == ["o1", "o2", "o3"]
    assert all(r["status"] == "resting" and r["unfilled_qty_units"] == digits and r["fills"] == [] for r in got)

"""Replay-layer error and compression contract tests."""

import gzip
import json
import re
import tempfile
import unittest
from pathlib import Path

from orderbook import BaselineOrderBook
from orderbook.replay import replay_file
from support import limit


class TestReplay(unittest.TestCase):
    def temporary_directory(self):
        return tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)

    def test_malformed_json_reports_resolved_path_and_line(self) -> None:
        with self.temporary_directory() as directory:
            path = Path(directory) / "malformed.jsonl"
            path.write_text(json.dumps(limit(1, "e1", "b", "BUY", 100, 1)) + "\n{bad json\n", encoding="utf-8")
            pattern = re.escape(str(path.resolve())) + r".*line 2"
            with self.assertRaisesRegex(ValueError, pattern):
                replay_file(path, BaselineOrderBook())

    def test_gzipped_jsonl_and_nonincreasing_sequence_rejection(self) -> None:
        with self.temporary_directory() as directory:
            path = Path(directory) / "events.jsonl.gz"
            events = [limit(10, "e1", "b1", "BUY", 100, 1), limit(10, "e2", "b2", "BUY", 99, 1)]
            with gzip.open(path, "wt", encoding="utf-8", newline="\n") as stream:
                for event in events:
                    stream.write(json.dumps(event) + "\n")
            results = replay_file(path, BaselineOrderBook())
            self.assertEqual(results[1], {"event_id": "e2", "status": "rejected", "reason": "nonincreasing_sequence"})


if __name__ == "__main__":
    unittest.main()


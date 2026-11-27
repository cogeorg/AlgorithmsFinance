"""A verifier must reject altered evidence even if CSV hashes are recomputed."""

from contextlib import redirect_stdout
import csv
import hashlib
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from run_bitcoin import run
from verify_results import verify_run


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(self.temp.cleanup)
        folder = Path(self.temp.name)
        source = folder / 'ETHUSDT.csv'
        source.write_text('timestamp_utc,close\n2026-01-01T00:00:00Z,100\n2026-01-01T01:00:00Z,102\n2026-01-01T02:00:00Z,101\n')
        self.output = folder / 'output'
        with redirect_stdout(StringIO()):
            run(source, 2, self.output, 'numpy')

    def test_valid_run(self):
        self.assertEqual(verify_run(self.output)['status'], 'verified')

    def test_rejects_changed_reported_price(self):
        path = self.output / 'result.json'
        result = json.loads(path.read_text())
        result['put_value'] += 1
        path.write_text(json.dumps(result))
        with self.assertRaises(ValueError):
            verify_run(self.output)

    def test_rejects_changed_crossing_even_with_updated_hash(self):
        path = self.output / 'boundary.csv'
        with path.open(newline='') as stream:
            reader = csv.DictReader(stream)
            fields, rows = reader.fieldnames, list(reader)
        rows[-1]['at_or_below_boundary'] = '1'
        with path.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        report = self.output / 'result.json'
        result = json.loads(report.read_text())
        result['result_file_sha256']['boundary.csv'] = hashlib.sha256(path.read_bytes()).hexdigest()
        report.write_text(json.dumps(result))
        with self.assertRaises(ValueError):
            verify_run(self.output)

    def test_rejects_unavailable_source_hash(self):
        path = self.output / 'result.json'
        result = json.loads(path.read_text())
        result['source_sha256']['tree_model.py'] = '0' * 64
        path.write_text(json.dumps(result))
        with self.assertRaises(ValueError):
            verify_run(self.output)


if __name__ == '__main__':
    unittest.main()

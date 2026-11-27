"""Whole-batch correctness and semantic rejection of altered batch evidence."""

from contextlib import redirect_stdout
import csv
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from price_american_put import price_american_put as scalar_price
from run_assets import run_horizon
from verify_assets import verify_batch
from verify_results import digest


class AssetBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.paths = []
        for name, prices in [('AAAUSDT', (100, 102, 101)), ('BBBUSDT', (50, 48, 49))]:
            path = self.root / (name + '.csv')
            path.write_text('timestamp_utc,close\n' + ''.join(f'2026-01-01T0{t}:00:00Z,{p}\n' for t, p in enumerate(prices)))
            self.paths.append(path)

    def run_batch(self):
        output = self.root / 'output'
        with redirect_stdout(StringIO()):
            result = run_horizon(self.paths[::-1], 2, output, 'fixture', expected_assets=2)
        return output, result

    def test_complete_batch_matches_scalar_prices(self):
        output, result = self.run_batch()
        self.assertEqual(result['asset_order'], ['AAAUSDT', 'BBBUSDT'])
        self.assertEqual(verify_batch(output, expected_assets=2)['status'], 'verified')
        inputs = json.loads((output / 'inputs.json').read_text())
        for case in inputs['cases']:
            m = case['input']['model']
            expected = scalar_price(m['spot'], m['strike'], m['up'], m['down'], m['gross_rate'], m['steps'])
            self.assertAlmostEqual(result['prices'][case['asset']], expected, places=10)
        self.assertEqual(result['assets'], 2)
        self.assertGreater(result['seconds'], 0)
        self.assertGreater(result['peak_traced_bytes'], 0)

    def test_duplicate_asset_is_rejected_before_output(self):
        output = self.root / 'output'
        with self.assertRaises(ValueError):
            run_horizon([self.paths[0], self.paths[0]], 2, output, 'fixture', expected_assets=2)
        self.assertFalse(output.exists())

    def test_missing_price_is_rejected(self):
        output, result = self.run_batch()
        del result['prices']['AAAUSDT']
        (output / 'batch.json').write_text(json.dumps(result))
        with self.assertRaises(ValueError):
            verify_batch(output, expected_assets=2)

    def test_changed_table_is_rejected_even_with_updated_hash(self):
        output, result = self.run_batch()
        path = output / 'prices.csv'
        with path.open(newline='') as stream:
            reader = csv.DictReader(stream)
            fields, rows = reader.fieldnames, list(reader)
        rows[0]['put_value'] = str(float(rows[0]['put_value']) + 1)
        with path.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        result['result_file_sha256']['prices.csv'] = digest(path)
        (output / 'batch.json').write_text(json.dumps(result))
        with self.assertRaises(ValueError):
            verify_batch(output, expected_assets=2)


if __name__ == '__main__':
    unittest.main()

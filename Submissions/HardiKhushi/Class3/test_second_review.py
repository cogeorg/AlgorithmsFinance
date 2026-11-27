"""Reproductions from the second independent review of the completed work."""

from contextlib import redirect_stdout
import csv
from datetime import datetime, timedelta, timezone
import hashlib
from io import StringIO
import json
from math import inf, nextafter
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import build_summary
from check_asset_numerics import check
from market_data import HERE, PriceWindow
from price_american_put import price_american_put as scalar
from price_american_put_numpy import price_american_put as vector
from run_bitcoin import run
from verify_submission import verify_summary


class SecondReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=HERE)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_tiny_positive_expiry_payoff_has_an_exercise_node(self):
        strike = nextafter(100., inf)
        for pricer in (scalar, vector):
            with self.subTest(engine=pricer.__module__):
                self.assertEqual(pricer(100, strike, 1.2, .8, 1.05, 0, return_boundary=True),
                                 (strike - 100, [100]))

    def test_expiry_only_subnormal_prices_are_supported(self):
        for pricer in (scalar, vector):
            with self.subTest(engine=pricer.__module__):
                value, boundary = pricer(1e-310, 2e-310, 1.2, .8, 1.05, 0, return_boundary=True)
                self.assertGreater(value, 0)
                self.assertEqual(boundary, [1e-310])

    def test_exact_root_payoff_is_not_filtered_as_stock_rounding_noise(self):
        strike = nextafter(100., inf)
        for pricer in (scalar, vector):
            with self.subTest(engine=pricer.__module__):
                value, boundary = pricer(100, strike, 1.2, 1.1, 1.15, 1, return_boundary=True)
                self.assertEqual(value, strike - 100)
                self.assertEqual(boundary[0], 100)

    def test_caller_mutation_cannot_invalidate_a_price_window(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        dates = [start + timedelta(hours=t) for t in range(3)]
        prices = [100., 101., 102.]
        window = PriceWindow(Path('fixture.csv'), 'fixture', 3, dates, prices)
        prices.pop()
        dates.append(start + timedelta(hours=3))
        self.assertEqual(window.prices, (100., 101., 102.))
        self.assertEqual(len(window.timestamps), 3)

    def summary_tree(self, duplicate_full=False, completion=True):
        bitcoin = self.root / 'results/audit_v1'
        bitcoin.mkdir(parents=True)
        for name in ('bitcoin_1y_numpy', 'bitcoin_full_numpy'):
            (bitcoin / name).symlink_to(HERE / 'results/audit_v1' / name, target_is_directory=True)
        assets = self.root / 'results/all_assets_v1'
        assets.mkdir(parents=True)
        identities = {}
        for horizon in ('1y', 'full'):
            source = HERE / 'results/all_assets_v1' / ('full' if duplicate_full else horizon)
            (assets / horizon).symlink_to(source, target_is_directory=True)
            identities[horizon] = hashlib.sha256((source / 'batch.json').read_bytes()).hexdigest()
        if completion:
            (assets / 'completion.json').write_text(json.dumps({'status': 'complete', 'batch_files': identities}))

    def test_summary_rejects_full_file_batch_reused_as_one_year(self):
        self.summary_tree(duplicate_full=True)
        with patch.object(build_summary, 'HERE', self.root), self.assertRaises((ValueError, OSError)):
            build_summary.build(self.root / 'summary.csv')

    def test_summary_requires_the_completed_two_horizon_run(self):
        self.summary_tree(completion=False)
        with patch.object(build_summary, 'HERE', self.root), self.assertRaises((ValueError, OSError)):
            build_summary.build(self.root / 'summary.csv')

    def test_numerical_checker_cannot_verify_zero_contracts(self):
        directory = self.root / 'batches'
        for horizon in ('1y', 'full'):
            folder = directory / horizon
            folder.mkdir(parents=True)
            source = HERE / 'results/all_assets_v1' / horizon
            result = json.loads((source / 'batch.json').read_text())
            inputs = json.loads((source / 'inputs.json').read_text())
            inputs['cases'] = []
            (folder / 'inputs.json').write_text(json.dumps(inputs))
            (folder / 'batch.json').write_text(json.dumps(result))
        with redirect_stdout(StringIO()), self.assertRaises(ValueError):
            check(directory)

    def test_non_bitcoin_console_unit_matches_the_actual_asset(self):
        source = self.root / 'ETHUSDT.csv'
        source.write_text('timestamp_utc,close\n2026-01-01T00:00:00Z,100\n2026-01-01T01:00:00Z,102\n2026-01-01T02:00:00Z,101\n')
        console = StringIO()
        with redirect_stdout(console):
            run(source, 2, self.root / 'output', 'numpy')
        self.assertIn('USDT/ETH', console.getvalue())
        self.assertNotIn('USDT/BTC', console.getvalue())

    def summary_copy(self):
        path = self.root / 'summary.csv'
        path.write_bytes((HERE / 'results/final_summary.csv').read_bytes())
        path.with_suffix('.manifest.json').write_bytes((HERE / 'results/final_summary.manifest.json').read_bytes())
        return path

    def test_delivered_summary_matches_all_four_measured_sources(self):
        self.assertEqual(verify_summary(self.summary_copy())['rows_verified'], 4)

    def test_changed_summary_is_rejected_even_after_hash_update(self):
        path = self.summary_copy()
        with path.open(newline='') as stream:
            reader = csv.DictReader(stream)
            fields, rows = reader.fieldnames, list(reader)
        rows[0]['horizon'] = 'full'
        with path.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        meta = path.with_suffix('.manifest.json')
        manifest = json.loads(meta.read_text())
        manifest['summary_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        meta.write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            verify_summary(path)


if __name__ == '__main__':
    unittest.main()

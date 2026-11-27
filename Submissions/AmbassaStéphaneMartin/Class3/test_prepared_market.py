"""Fast integration with prepared Bitcoin CSVs; no tree pricing or real calibration."""
from collections import deque
import csv
import json
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import market_test_support as support

ROOT = Path(__file__).resolve().parent


class PreparedBitcoinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.year = support.load_prepared_window('BTCUSDT', 'one_year')
        cls.full = support.load_prepared_window('BTCUSDT', 'full_history')
        manifest = json.loads((ROOT / 'data' / 'source_manifest.json').read_text(encoding='utf-8'))
        raw_path = next(entry['file'] for entry in manifest['files'] if entry['asset'] == 'BTCUSDT')
        with (ROOT / raw_path).open(newline='', encoding='utf-8') as stream:
            cls.raw_tail = deque(csv.DictReader(stream), maxlen=8761)

    def test_one_year_has_8761_closes_and_8760_changes(self):
        self.assertEqual(len(self.year.prices), 8761)
        self.assertEqual(len(self.year.prices)-1, 8760)
        self.assertEqual(int(self.year.metadata['N']), 8760)
        self.assertEqual(self.year.labels[0], 'P_0')
        self.assertEqual(self.year.labels[-1], 'P_8760')
        self.assertEqual(self.year.indices, tuple(range(8761)))

    def test_S0_and_K_are_first_selected_close(self):
        first = Decimal(self.raw_tail[0]['close'])
        self.assertEqual(Decimal(str(self.year.prices[0])), first)
        self.assertEqual(Decimal(self.year.metadata['P_0']), first)
        self.assertEqual(Decimal(self.year.metadata['S_0']), first)
        self.assertEqual(Decimal(self.year.metadata['K']), first)
        # A calibration-shaped test double checks wiring only; no pricing call.
        model = SimpleNamespace(N=8760, u=1.2, d=0.8, R=1.05)
        inputs = support.pricing_parameters(self.year, model)
        self.assertEqual(inputs['S0'], inputs['K'])
        self.assertEqual(inputs['S0'], self.year.prices[0])
        self.assertEqual(inputs['N'], 8760)

    def test_selected_endpoints_match_raw_tail_and_actual_one_year(self):
        parse = lambda text: datetime.fromisoformat(text.replace('Z', '+00:00'))
        self.assertEqual(self.year.timestamps[0], parse(self.raw_tail[0]['timestamp_utc']))
        self.assertEqual(self.year.timestamps[-1], parse(self.raw_tail[-1]['timestamp_utc']))
        self.assertEqual(self.year.timestamps[-1]-self.year.timestamps[0], timedelta(hours=8760))
        self.assertEqual(support.require_hourly_window(self.year), 1.0)

    def test_calibration_receives_8761_closes_and_one_elapsed_year(self):
        sentinel = object()
        with patch('market_test_support.market_calibration.calibrate_binomial', return_value=sentinel) as calibrate:
            actual = support.calibrate_prepared_window(self.year)
        self.assertIs(actual, sentinel)
        calibrate.assert_called_once_with(self.year.prices, T=1.0, annual_rate=0.04)

    def test_full_history_gap_is_preserved_and_flagged(self):
        gaps = [(a, b) for a, b in zip(self.full.timestamps, self.full.timestamps[1:]) if b-a != timedelta(hours=1)]
        self.assertEqual(len(gaps), 1)
        a, b = gaps[0]
        self.assertEqual(b-a, timedelta(hours=2))
        self.assertEqual((a+timedelta(hours=1)).isoformat(), '2023-03-24T13:00:00+00:00')
        self.assertEqual(self.full.metadata['missing_hours'], '1')
        self.assertEqual(self.full.metadata['consecutive_hours'], 'False')
        self.assertEqual(self.full.metadata['ready_for_hourly_pricing'], 'False')
        self.assertEqual(self.full.metadata['status'], 'gaps_require_explicit_treatment')

    def test_gap_is_rejected_before_calibration_is_called(self):
        with patch('market_test_support.market_calibration.calibrate_binomial') as calibrate:
            with self.assertRaisesRegex(ValueError, 'explicit treatment'):
                support.calibrate_prepared_window(self.full)
            calibrate.assert_not_called()

    def test_gap_cannot_be_hidden_by_changing_only_the_metadata_flag(self):
        changed = replace(self.full, metadata={**self.full.metadata, 'ready_for_hourly_pricing': 'True'})
        with patch('market_test_support.market_calibration.calibrate_binomial') as calibrate:
            with self.assertRaisesRegex(ValueError, 'explicit treatment'):
                support.calibrate_prepared_window(changed)
            calibrate.assert_not_called()

    def test_preparation_flag_is_honored_even_when_hours_are_consecutive(self):
        changed = replace(self.year, metadata={**self.year.metadata, 'ready_for_hourly_pricing': 'False'})
        with patch('market_test_support.market_calibration.calibrate_binomial') as calibrate:
            with self.assertRaisesRegex(ValueError, 'explicit treatment'):
                support.calibrate_prepared_window(changed)
            calibrate.assert_not_called()


class ExecutionSafetyTests(unittest.TestCase):
    def test_expensive_files_and_groups_are_outside_default_discovery(self):
        from fnmatch import fnmatch
        import run_tests
        groups = ' '.join(module for _, module in run_tests.SUITES)
        for name in ('bitcoin_integration_check', 'benchmark_pricing'):
            with self.subTest(module=name):
                self.assertNotIn(name, groups)
                self.assertFalse(fnmatch(name+'.py', 'test*.py'))

    def test_benchmark_requires_explicit_opt_in_before_any_work(self):
        from contextlib import redirect_stderr
        import io
        import benchmark_pricing
        with patch('sys.argv', ['benchmark_pricing.py']), redirect_stderr(io.StringIO()):
            with patch('benchmark_pricing.benchmark') as benchmark:
                with patch('benchmark_pricing.support.calibrate_prepared_window') as calibrate:
                    with self.assertRaises(SystemExit) as exit_result:
                        benchmark_pricing.main()
                    self.assertEqual(exit_result.exception.code, 2)
                    benchmark.assert_not_called()
                    calibrate.assert_not_called()

    def test_optional_bitcoin_case_skips_without_opt_in(self):
        import bitcoin_integration_check
        self.assertFalse(bitcoin_integration_check.RUN_BITCOIN)
        case = bitcoin_integration_check.OptionalBitcoinIntegration('test_one_year_finite_price_and_boundary_dimensions')
        result = unittest.TestResult()
        with patch('bitcoin_integration_check.support.load_prepared_window') as load:
            case.run(result)
            load.assert_not_called()
        self.assertEqual(len(result.skipped), 1)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.failures, [])

if __name__ == '__main__':
    unittest.main()
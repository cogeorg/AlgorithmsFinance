"""Behavioral checks for data loss, period selection, and visible time gaps."""
import csv
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import prepare_data as prep


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.path = self.root / 'BTCUSDT.csv'

    def tearDown(self):
        self.temporary.cleanup()

    def load(self, rows):
        with self.path.open('w', newline='', encoding='utf-8') as stream:
            writer = csv.writer(stream)
            writer.writerow(['timestamp_utc', 'close'])
            writer.writerows(rows)
        return prep.load_asset(self.path)

    def test_unsorted_input_is_audited_and_raw_bytes_are_unchanged(self):
        data = self.load([('2026-01-01T02:00:00Z', '3'),
                          ('2026-01-01T00:00:00Z', '1'),
                          ('2026-01-01T01:00:00Z', '2')])
        before = self.path.read_bytes()
        self.assertEqual([r.close for r in data.observations], [Decimal(1), Decimal(2), Decimal(3)])
        self.assertEqual(data.summary['ordering_violations'], 1)
        self.assertFalse(data.summary['raw_chronological_non_decreasing'])
        prep.load_asset(self.path)
        self.assertEqual(self.path.read_bytes(), before)

    def test_identical_duplicates_and_conflicting_duplicates_have_distinct_policies(self):
        data = self.load([('2026-01-01T00:00:00Z', '10'),
                          ('2026-01-01T00:00:00Z', '10.00'),
                          ('2026-01-01T01:00:00Z', '11'),
                          ('2026-01-01T01:00:00Z', '12'),
                          ('2026-01-01T02:00:00Z', '13')])
        self.assertEqual(len(data.observations), 2)
        self.assertEqual(data.observations[0].source_row, 2)
        self.assertEqual(data.observations[0].close_text, '10')
        self.assertEqual(data.summary['duplicate_timestamp_rows'], 2)
        self.assertEqual(data.summary['duplicate_timestamp_groups'], 2)
        self.assertEqual(data.summary['conflicting_duplicate_timestamp_groups'], 1)
        self.assertEqual(data.summary['excluded_rows'], 3)
        self.assertEqual(data.summary['missing_hours'], 1)
        self.assertEqual(CounterReasons(data.exclusions), {
            'identical_duplicate_timestamp': 1, 'conflicting_duplicate_timestamp': 2})

    def test_invalid_prices_do_not_invent_replacement_observations(self):
        bad = ['0', '-1', 'NaN', 'Infinity', '-Infinity', 'not-a-price', '']
        start = datetime(2026, 1, 1, tzinfo=prep.UTC)
        rows = [(prep.iso(start), '10')]
        rows += [(prep.iso(start + i * prep.HOUR), value) for i, value in enumerate(bad, 1)]
        rows.append((prep.iso(start + 8 * prep.HOUR), '11'))
        data = self.load(rows)
        self.assertEqual(data.summary['invalid_prices'], 7)
        self.assertEqual(data.summary['excluded_rows'], 7)
        self.assertEqual(data.summary['missing_hours'], 7)
        self.assertEqual(len(data.observations), 2)

    def test_invalid_naive_and_off_hour_timestamps_are_excluded(self):
        data = self.load([('bad-date', '2'), ('2026-01-01T00:00:00', '2'),
                          ('2026-01-01T00:30:00Z', '2'), ('2026-01-01T01:00:00Z', '2')])
        self.assertEqual(data.summary['invalid_timestamps'], 2)
        self.assertEqual(data.summary['off_hour_timestamps'], 1)
        self.assertEqual(data.summary['excluded_rows'], 3)
        self.assertEqual(len(data.observations), 1)
        self.assertFalse(prep.select_window(data, 'full_history').summary()['ready_for_hourly_pricing'])

    def test_offsets_normalize_to_same_utc_hour(self):
        data = self.load([('2026-01-01T01:00:00+01:00', '10'),
                          ('2026-01-01T00:00:00Z', '10'),
                          ('2026-01-01T01:00:00Z', '11')])
        self.assertEqual(len(data.observations), 2)
        self.assertEqual(data.summary['duplicate_timestamp_rows'], 1)
        self.assertTrue(data.summary['consecutive_hours'])

    def test_one_year_uses_exact_last_8761_closes_and_first_selected_contract(self):
        start = datetime(2025, 1, 1, tzinfo=prep.UTC)
        data = self.load([(prep.iso(start + i * prep.HOUR), str(100+i)) for i in range(8762)])
        window = prep.select_window(data, 'one_year')
        row = window.summary()
        self.assertEqual(row['observations'], 8761)
        self.assertEqual(row['N'], 8760)
        self.assertEqual(row['start_utc'], prep.iso(start + prep.HOUR))
        self.assertEqual(row['elapsed_hours'], 8760)
        self.assertEqual((row['P_0'], row['S_0'], row['K']), ('101', '101', '101'))
        self.assertTrue(row['ready_for_hourly_pricing'])
        self.assertEqual(row['last_label'], 'P_8760')

    def test_enough_observations_with_gap_is_not_ready_for_hourly_pricing(self):
        start = datetime(2025, 1, 1, tzinfo=prep.UTC)
        rows = [(prep.iso(start + i * prep.HOUR), '100') for i in range(8762) if i != 3000]
        data = self.load(rows)
        row = prep.select_window(data, 'one_year').summary()
        self.assertEqual(row['N'], 8760)
        self.assertEqual(row['elapsed_hours'], 8761)
        self.assertEqual(row['missing_hours'], 1)
        self.assertTrue(row['sufficient_observations'])
        self.assertFalse(row['ready_for_hourly_pricing'])
        self.assertEqual(row['status'], 'gaps_require_explicit_treatment')

    def test_short_history_is_not_mislabelled_as_one_year(self):
        data = self.load([('2026-01-01T00:00:00Z', '1'), ('2026-01-01T01:00:00Z', '2')])
        one = prep.select_window(data, 'one_year').summary()
        self.assertEqual(one['available_observations'], 2)
        self.assertEqual(one['observations'], 0)
        self.assertIsNone(one['N'])
        self.assertEqual(one['status'], 'insufficient_observations')
        self.assertTrue(prep.select_window(data, 'full_history').summary()['ready_for_hourly_pricing'])
        self.assertFalse(data.summary['complete_course_five_year_grid'])

    def test_full_history_calendar_cap_and_leap_day(self):
        data = self.load([('2021-02-28T00:00:00Z', '1'),
                          ('2021-02-28T01:00:00Z', '2'),
                          ('2026-02-28T00:00:00Z', '3')])
        window = prep.select_window(data, 'full_history')
        self.assertEqual(len(window.observations), 2)
        self.assertEqual(window.observations[0].close_text, '2')
        self.assertEqual(prep.calendar_years_ago(datetime(2024,2,29,tzinfo=prep.UTC), 5),
                         datetime(2019,2,28,tzinfo=prep.UTC))
        self.assertEqual(prep.COURSE_HOURS, 43824)  # independent count includes the 2024 leap day

    def test_boundary_omissions_are_not_hidden_by_internal_gap_count(self):
        data = self.load([('2021-11-01T01:00:00Z', '1'), ('2021-11-01T02:00:00Z', '2')])
        self.assertEqual(data.summary['missing_hours'], 0)
        self.assertEqual(data.summary['missing_course_hours'], 43822)
        self.assertFalse(data.summary['complete_course_five_year_grid'])

    def test_export_retains_gap_duration_labels_and_source_lines(self):
        data = self.load([('2026-01-01T00:00:00Z', '10.1200'),
                          ('2026-01-01T03:00:00Z', '12')])
        path = self.root / 'selected.csv'
        prep.export_window(prep.select_window(data, 'full_history'), path)
        with path.open(newline='') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(rows[0]['observation_label'], 'P_0')
        self.assertEqual(rows[0]['close'], '10.1200')
        self.assertEqual(rows[0]['source_row'], '2')
        self.assertEqual(rows[0]['elapsed_hours_from_previous'], '')
        self.assertEqual(rows[1]['observation_label'], 'P_1')
        self.assertEqual(rows[1]['elapsed_hours_from_previous'], '3')
        self.assertEqual(rows[1]['missing_hours_before'], '2')

    def test_empty_history_reports_unavailable_instead_of_ready(self):
        data = self.load([])
        self.assertEqual(data.summary['usable_observations'], 0)
        self.assertFalse(data.summary['consecutive_hours'])
        for name in ('one_year', 'full_history'):
            self.assertFalse(prep.select_window(data, name).summary()['sufficient_observations'])

    def test_schema_errors_fail_instead_of_silently_renaming_columns(self):
        self.path.write_text('date,price\n2026-01-01,10\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'expected timestamp_utc,close'):
            prep.load_asset(self.path)

    def test_malformed_records_are_logged_and_excluded_once(self):
        self.path.write_text('timestamp_utc,close\n2026-01-01T00:00:00Z,2,extra\n'
                             '2026-01-01T01:00:00Z\n2026-01-01T02:00:00Z,3\n', encoding='utf-8')
        data = prep.load_asset(self.path)
        self.assertEqual(data.summary['raw_observations'], 3)
        self.assertEqual(data.summary['malformed_rows'], 2)
        self.assertEqual(data.summary['invalid_prices'], 1)
        self.assertEqual(data.summary['excluded_rows'], 2)
        self.assertEqual(len(data.observations), 1)


class SnapshotAcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name)
        self.project = self.repo / 'Submissions' / 'Student' / 'Class3'
        self.data = self.project / 'data'
        (self.data / 'hourly').mkdir(parents=True)
        for symbol in prep.SYMBOLS:
            (self.data / 'hourly' / f'{symbol}.csv').write_text(
                'timestamp_utc,close\n2026-01-01T00:00:00Z,100\n', encoding='utf-8')
        for filename in ('README.md', 'fetch_sp500.py', 'build_hourly_data.py'):
            (self.data / filename).write_text(filename, encoding='utf-8')
        # An unrelated course copy must not replace the selected local dataset.
        (self.repo / 'Class3' / 'data' / 'hourly').mkdir(parents=True)
        inspect_git = patch.object(prep, 'git_read', side_effect=lambda repo, *args:
                                  'source-commit' if args == ('rev-parse', 'HEAD') else '')
        inspect_git.start()
        self.addCleanup(inspect_git.stop)

    def test_local_inputs_are_registered_without_copying_or_changing_them(self):
        before = {path: prep.sha256(path) for path in self.data.rglob('*') if path.is_file()}
        manifest = prep.acquire_snapshot(self.repo, self.project)
        self.assertEqual(len(manifest['files']), 40)
        self.assertTrue(all(entry['file'].startswith('data/hourly/') for entry in manifest['files']))
        self.assertFalse((self.data / 'raw').exists())
        self.assertFalse((self.project / 'reference' / 'course_data').exists())
        self.assertEqual(before, {path: prep.sha256(path) for path in before})
        self.assertEqual(prep.verify_snapshot(self.project), manifest)
        self.assertEqual(prep.acquire_snapshot(self.repo, self.project), manifest)

    def test_registered_input_changes_are_detected(self):
        prep.acquire_snapshot(self.repo, self.project)
        (self.data / 'hourly' / 'BTCUSDT.csv').write_text('changed input', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'integrity check failed'):
            prep.verify_snapshot(self.project)


def CounterReasons(exclusions):
    from collections import Counter
    return dict(Counter(row['reason'] for row in exclusions))


if __name__ == '__main__':
    unittest.main()

"""Run all unittest suites; distinguish pending implementation from other failures."""
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent
WINDOW_SUMMARY = ('output/window_summary.csv' if (ROOT / 'output/window_summary.csv').is_file()
                  else 'results/window_summary.csv')
PROTECTED = ('prepare_data.py', 'test_prepare_data.py', 'README.md', 'data/source_manifest.json',
             'american_put.py', 'test_american_put.py', 'market_calibration.py', 'test_market_calibration.py',
             'test_american_put_properties.py', WINDOW_SUMMARY,
             'output/windows/BTCUSDT/one_year.csv', 'output/windows/BTCUSDT/full_history.csv')
SUITES = (
    ('pricing', 'test_american_put'),
    ('scalar_numerics', 'test_american_put_numerics'),
    ('full_tree_reference', 'test_american_put_properties.FullTreeReferenceTests'),
    ('financial_properties', 'test_american_put_properties.AmericanPutPropertyTests'),
    ('calibration', 'test_market_calibration'),
    ('boundary_reference', 'test_exercise_policy.BoundaryReferenceTests'),
    ('exercise_boundary', 'test_exercise_policy.ExerciseBoundaryTests'),
    ('observed_exercise', 'test_exercise_policy.ObservedExerciseTests'),
    ('market_experiments', 'test_market_experiments'),
    ('prepared_market', 'test_prepared_market'),
    ('data_preparation', 'test_prepare_data'),
)
PENDING_MARKERS = (
    'test_american_put.PricingNotImplemented: PENDING_IMPLEMENTATION:',
    'test_market_calibration.CalibrationNotImplemented: PENDING_IMPLEMENTATION:',
    'test_exercise_policy.ExerciseNotImplemented: PENDING_IMPLEMENTATION:',
)


def protected_hashes():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in PROTECTED}


def run_suite(module, output, name):
    log = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromName(module)
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    (output / f'{name}.log').write_text(log.getvalue(), encoding='utf-8')
    pending = []
    other = []
    for test, trace in result.failures:
        (pending if any(marker in trace for marker in PENDING_MARKERS) else other).append(str(test))
    return result, {
        'test_methods_run': result.testsRun,
        'expected_red_failures_missing_implementation': len(pending),
        'other_assertion_failures': len(other),
        'unittest_errors': len(result.errors),
        'unittest_expected_failure_decorators': len(result.expectedFailures),
        'skipped': len(result.skipped),
        'passed': result.wasSuccessful(),
        'pending_cases': pending,
        'other_failure_cases': other,
        'error_cases': [str(test) for test, _ in result.errors],
        'log': f'{name}.log',
    }


def main():
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    output = ROOT / 'output' / 'pricing_tests'
    output.mkdir(parents=True, exist_ok=True)
    before = protected_hashes()
    details = {}
    results = []
    for name, module in SUITES:
        result, details[name] = run_suite(module, output, name)
        results.append(result)
    after = protected_hashes()
    preserved = {name: before[name] == after[name] for name in PROTECTED}
    status = {
        'interface': 'american_put.price_american_put(S0, K, u, d, R, N) -> float',
        'calibration_interfaces': [
            'market_calibration.log_returns(prices) -> tuple[float, ...]',
            'market_calibration.sample_hourly_volatility(returns) -> float',
            'market_calibration.calibrate_binomial(prices, *, T, annual_rate=0.04) -> Calibration',
        ],
        'exercise_interfaces': [
            'exercise_policy.price_american_put_with_boundary(S0, K, u, d, R, N) -> PutExerciseResult',
            'exercise_policy.first_observed_exercise(prices, boundary, K, *, timestamps_utc) -> ObservedExercise',
        ],
        'expensive_runs_in_default_suite': False,
        **details,
        'existing_files_unchanged': preserved, 'existing_files_sha256': after,
        'python': sys.version,
    }
    (output / 'status.json').write_text(json.dumps(status, indent=2) + '\n', encoding='utf-8')
    compact = {
        name: {key: value for key, value in group.items()
               if key not in ('pending_cases', 'other_failure_cases', 'error_cases')}
        for name, group in details.items()
    }
    compact['existing_files_unchanged'] = preserved
    print(json.dumps(compact, indent=2))
    print(f'Detailed results: {output / "status.json"}')
    # All ordinary failure semantics remain active while implementation is pending.
    return 0 if all(result.wasSuccessful() for result in results) and all(preserved.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())

"""Opt-in pricing benchmark, with separate timing and memory passes.

No timing limits or performance assertions. No pricing runs at import time.
"""
import argparse
import gc
import json
import math
from pathlib import Path
import platform
import sys
from time import perf_counter
import tracemalloc

import american_put
import exercise_policy
import market_test_support as support

ROOT = Path(__file__).resolve().parent


def process_peak_memory():
    """Whole-process high-water RSS/working set, in bytes; not call-only memory."""
    try:
        if sys.platform == 'win32':
            import ctypes
            from ctypes import wintypes

            class Counters(ctypes.Structure):
                _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
                    (name, ctypes.c_size_t) for name in (
                        'PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
                        'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
                        'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.GetCurrentProcess.restype = wintypes.HANDLE
            psapi = ctypes.WinDLL('psapi', use_last_error=True)
            psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            counters = Counters()
            counters.cb = ctypes.sizeof(counters)
            if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
                raise ctypes.WinError(ctypes.get_last_error())
            return counters.PeakWorkingSetSize, 'Windows PeakWorkingSetSize, whole-process high-water mark'
        import resource
        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(value if sys.platform == 'darwin' else value*1024), 'resource.ru_maxrss, whole-process high-water mark'
    except (ImportError, OSError, AttributeError):
        return None, 'Process peak memory unavailable; peak traced Python bytes still reported'


def extract_result(result, kind, periods):
    value = result.price if kind == 'boundary' else result
    if not math.isfinite(value):
        raise ValueError('Benchmark result price is not finite.')
    dimensions = len(result.boundary) if kind == 'boundary' else None
    if dimensions is not None and dimensions != periods+1:
        raise ValueError('Boundary dimensions disagree with N+1.')
    return float(value), dimensions


def benchmark(function, inputs, kind):
    gc.collect()
    start = perf_counter()
    timed = function(**inputs)
    seconds = perf_counter()-start
    value, dimension = extract_result(timed, kind, inputs['N'])
    del timed
    gc.collect()
    tracemalloc.start()
    try:
        memory_start = perf_counter()
        measured = function(**inputs)
        memory_seconds = perf_counter()-memory_start
        _, peak = tracemalloc.get_traced_memory()
        memory_value, memory_dimension = extract_result(measured, kind, inputs['N'])
    finally:
        tracemalloc.stop()
    if not math.isclose(value, memory_value, rel_tol=1e-12, abs_tol=1e-12) or dimension != memory_dimension:
        raise ValueError('Timing and memory passes returned inconsistent results.')
    process_peak, process_scope = process_peak_memory()
    return {
        'elapsed_seconds_untraced': seconds,
        'peak_traced_python_bytes': peak,
        'memory_pass_elapsed_seconds_traced': memory_seconds,
        'process_peak_memory_bytes': process_peak, 'process_peak_scope': process_scope,
        'price': value, 'boundary_entries': dimension,
        'timing_runs': 1, 'memory_runs': 1,
        'memory_notes': 'Traced peak covers allocations during pricing only; process peak includes imports, data and both passes.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true', help='Explicitly allow TWO production pricing calls.')
    parser.add_argument('--kind', choices=('scalar', 'boundary'), default='scalar')
    parser.add_argument('--periods', type=int, help='Synthetic case N; defaults to 32. Do not combine with --asset.')
    parser.add_argument('--asset', help='Prepared course asset, for example BTCUSDT.')
    parser.add_argument('--window', choices=('one_year', 'full_history'), help='Prepared window, default one_year.')
    parser.add_argument('--output', type=Path, help='JSON output path; default output/benchmarks/<case>.json.')
    args = parser.parse_args()
    if not args.run:
        parser.error('No benchmark ran. Use --run to opt in to timing AND memory pricing passes.')
    if args.asset and args.periods is not None:
        parser.error('--asset and --periods are separate benchmark cases.')
    if args.window and not args.asset:
        parser.error('--window requires --asset.')
    try:
        if args.asset:
            name = args.window or 'one_year'
            window = support.load_prepared_window(args.asset, name)
            model = support.calibrate_prepared_window(window)
            inputs = support.pricing_parameters(window, model)
            case = f'{args.asset}_{name}'
            data_info = {key: window.metadata[key] for key in ('start_utc', 'end_utc', 'elapsed_hours', 'file')}
        else:
            periods = args.periods if args.periods is not None else 32
            if periods < 0:
                parser.error('--periods must be nonnegative.')
            inputs = dict(S0=100.0, K=100.0, u=1.02, d=1/1.02, R=math.exp(0.04/8760), N=periods)
            case, data_info = 'synthetic', None
        function = american_put.price_american_put if args.kind == 'scalar' else exercise_policy.price_american_put_with_boundary
        metrics = benchmark(function, inputs, args.kind)
    except NotImplementedError as exc:
        print(f'PENDING_IMPLEMENTATION: {exc}. No benchmark measurements were saved.', file=sys.stderr)
        return 2
    except (ValueError, MemoryError) as exc:
        print(f'Benchmark stopped: {exc}. No benchmark measurements were saved.', file=sys.stderr)
        return 2
    result = {
        'case': case, 'kind': args.kind, 'assets': 1, 'parameters': inputs,
        'data': data_info, 'python': sys.version, 'platform': platform.platform(),
        'timing_scope': 'Production pricing only; data loading and calibration excluded.',
        **metrics,
    }
    output = args.output or ROOT / 'output' / 'benchmarks' / f'{case}_{args.kind}_N{inputs["N"]}.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
    print(f'Saved: {output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
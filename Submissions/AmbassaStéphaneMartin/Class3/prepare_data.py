#!/usr/bin/env python3
"""Prepare the PriceAmericanPut lab data; standard library, Python >= 3.10.

Raw inputs are immutable. No interpolation, returns, calibration, or pricing.
Run ``python prepare_data.py --help`` for acquisition and preparation options.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Iterable

UTC = timezone.utc
HOUR = timedelta(hours=1)
COURSE_START = datetime(2021, 11, 1, tzinfo=UTC)
COURSE_END = datetime(2026, 10, 31, 23, tzinfo=UTC)
COURSE_HOURS = int((COURSE_END - COURSE_START) / HOUR) + 1
ONE_YEAR_CLOSES = 8761
REPOSITORY_URL = 'https://github.com/cogeorg/AlgorithmsFinance.git'
SYMBOLS = tuple(sorted('''BTCUSDT PAXGUSDT ETHUSDT BNBUSDT XRPUSDT ADAUSDT
SOLUSDT DOGEUSDT DOTUSDT LTCUSDT LINKUSDT BCHUSDT TRXUSDT AVAXUSDT ATOMUSDT
XLMUSDT ETCUSDT FILUSDT UNIUSDT NEARUSDT ALGOUSDT ICPUSDT AAVEUSDT VETUSDT
HBARUSDT SANDUSDT MANAUSDT AXSUSDT EGLDUSDT THETAUSDT XTZUSDT GRTUSDT
CHZUSDT CRVUSDT COMPUSDT SNXUSDT ENJUSDT ZECUSDT DASHUSDT NEOUSDT'''.split()))


def iso(value: datetime | None) -> str:
    return value.astimezone(UTC).isoformat().replace('+00:00', 'Z') if value else ''


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, fields: list[str], rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)


@dataclass(frozen=True)
class Observation:
    timestamp: datetime
    close: Decimal
    close_text: str
    source_row: int


@dataclass
class AssetData:
    asset: str
    observations: list[Observation]
    summary: dict
    exclusions: list[dict]
    gaps: list[dict]


@dataclass
class Window:
    asset: str
    name: str
    observations: list[Observation]
    available_observations: int
    sufficient_observations: bool
    lower_bound_exclusive: datetime | None = None

    def summary(self) -> dict:
        rows = self.observations
        gaps = find_gaps(rows, self.asset)
        elapsed = (rows[-1].timestamp - rows[0].timestamp) / HOUR if rows else None
        n = len(rows) - 1 if rows else None
        consecutive = len(rows) >= 2 and all(
            b.timestamp - a.timestamp == HOUR for a, b in zip(rows, rows[1:])
        )
        ready = self.sufficient_observations and consecutive
        status = ('ready' if ready else 'gaps_require_explicit_treatment'
                  if self.sufficient_observations else 'insufficient_observations')
        return {
            'asset': self.asset, 'window': self.name, 'quote_currency': 'USDT',
            'available_observations': self.available_observations,
            'required_observations': ONE_YEAR_CLOSES if self.name == 'one_year' else 2,
            'observations': len(rows), 'N': n,
            'first_label': 'P_0' if rows else '',
            'last_label': f'P_{n}' if rows else '',
            'start_utc': iso(rows[0].timestamp) if rows else '',
            'end_utc': iso(rows[-1].timestamp) if rows else '',
            'elapsed_hours': elapsed,
            'elapsed_days': elapsed / 24 if elapsed is not None else None,
            'elapsed_duration': str(rows[-1].timestamp - rows[0].timestamp) if rows else '',
            'P_0': rows[0].close_text if rows else '',
            'S_0': rows[0].close_text if rows else '',
            'K': rows[0].close_text if rows else '',
            'consecutive_hours': consecutive,
            'gap_count': len(gaps), 'missing_hours': sum(g['missing_hours'] for g in gaps),
            'largest_gap_missing_hours': max((g['missing_hours'] for g in gaps), default=0),
            'sufficient_observations': self.sufficient_observations,
            'ready_for_hourly_pricing': ready, 'status': status,
            'lower_bound_exclusive_utc': iso(self.lower_bound_exclusive),
        }


def find_gaps(rows: list[Observation], asset: str) -> list[dict]:
    """Internal absent UTC hours only; boundary omissions are reported separately."""
    gaps = []
    for a, b in zip(rows, rows[1:]):
        delta = b.timestamp - a.timestamp
        if delta > HOUR:
            gaps.append({
                'asset': asset, 'previous_timestamp_utc': iso(a.timestamp),
                'next_timestamp_utc': iso(b.timestamp),
                'first_missing_utc': iso(a.timestamp + HOUR),
                'last_missing_utc': iso(b.timestamp - HOUR),
                'missing_hours': int(delta / HOUR) - 1, 'elapsed_hours': int(delta / HOUR),
            })
    return gaps


def load_asset(path: Path) -> AssetData:
    """Audit raw rows, exclude invalid rows, resolve duplicates, and sort a copy.

    Invalid means malformed record, unparseable/naive/off-hour timestamp, or
    nonnumeric/nonfinite/nonpositive close. Equal-price duplicate hours retain
    the first valid source row. ALL valid rows at a conflicting-price duplicate
    hour are excluded, rather than guessing which price is correct.
    """
    asset = path.stem
    candidates = defaultdict(list)
    raw_times = []
    exclusions = []
    counts = Counter()
    with path.open('r', encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream, strict=True)
        if reader.fieldnames != ['timestamp_utc', 'close']:
            raise ValueError(f'{path}: expected timestamp_utc,close; got {reader.fieldnames!r}')
        for record in reader:
            counts['raw_observations'] += 1
            source_row = reader.line_num  # header is physical line 1
            reasons = []
            if None in record or any(value is None for value in record.values()):
                counts['malformed_rows'] += 1
                reasons.append('malformed_record')
            text_time = (record.get('timestamp_utc') or '').strip()
            text_price = (record.get('close') or '').strip()
            stamp = None
            try:
                stamp = datetime.fromisoformat(text_time.replace('Z', '+00:00'))
                if stamp.tzinfo is None or stamp.utcoffset() is None:
                    raise ValueError('timezone missing')
                stamp = stamp.astimezone(UTC)
                raw_times.append(stamp)
                if stamp.minute or stamp.second or stamp.microsecond:
                    counts['off_hour_timestamps'] += 1
                    reasons.append('timestamp_not_on_utc_hour')
            except (ValueError, OverflowError):
                counts['invalid_timestamps'] += 1
                reasons.append('invalid_or_naive_timestamp')
            price = None
            try:
                price = Decimal(text_price)
                if not price.is_finite() or price <= 0:
                    raise ValueError('price must be finite and positive')
            except (InvalidOperation, ValueError):
                counts['invalid_prices'] += 1
                reasons.append('invalid_price')
            item = {
                'asset': asset, 'source_row': source_row,
                'timestamp_raw': text_time, 'close_raw': text_price,
            }
            if reasons:
                exclusions.append({**item, 'reason': ';'.join(reasons)})
            else:
                candidates[stamp].append(Observation(stamp, price, text_price, source_row))

    clean = []
    conflict_groups = 0
    identical_removed = 0
    for stamp, group in sorted(candidates.items()):
        if len({row.close for row in group}) > 1:
            conflict_groups += 1
            for row in group:
                exclusions.append({
                    'asset': asset, 'source_row': row.source_row,
                    'timestamp_raw': iso(stamp), 'close_raw': row.close_text,
                    'reason': 'conflicting_duplicate_timestamp',
                })
        else:
            clean.append(group[0])
            for row in group[1:]:
                identical_removed += 1
                exclusions.append({
                    'asset': asset, 'source_row': row.source_row,
                    'timestamp_raw': iso(stamp), 'close_raw': row.close_text,
                    'reason': 'identical_duplicate_timestamp',
                })
    duplicate_counts = Counter(raw_times)
    violations = sum(a > b for a, b in zip(raw_times, raw_times[1:]))
    gaps = find_gaps(clean, asset)
    in_course = sum(COURSE_START <= row.timestamp <= COURSE_END for row in clean)
    consecutive = len(clean) >= 2 and all(
        b.timestamp - a.timestamp == HOUR for a, b in zip(clean, clean[1:])
    )
    summary = {
        'asset': asset, 'file': f'data/raw/{path.name}',
        'quote_currency': 'USDT', 'timestamp_column': 'timestamp_utc', 'close_column': 'close',
        'raw_observations': counts['raw_observations'], 'usable_observations': len(clean),
        'raw_start_utc': iso(min(raw_times)) if raw_times else '',
        'raw_end_utc': iso(max(raw_times)) if raw_times else '',
        'start_utc': iso(clean[0].timestamp) if clean else '',
        'end_utc': iso(clean[-1].timestamp) if clean else '',
        'raw_chronological_non_decreasing': violations == 0, 'ordering_violations': violations,
        'duplicate_timestamp_rows': sum(n - 1 for n in duplicate_counts.values()),
        'duplicate_timestamp_groups': sum(n > 1 for n in duplicate_counts.values()),
        'conflicting_duplicate_timestamp_groups': conflict_groups,
        'identical_duplicate_rows_removed': identical_removed,
        'invalid_timestamps': counts['invalid_timestamps'], 'invalid_prices': counts['invalid_prices'],
        'off_hour_timestamps': counts['off_hour_timestamps'], 'malformed_rows': counts['malformed_rows'],
        'excluded_rows': len(exclusions), 'gap_count': len(gaps),
        'missing_hours': sum(g['missing_hours'] for g in gaps),
        'largest_gap_missing_hours': max((g['missing_hours'] for g in gaps), default=0),
        'consecutive_hours': consecutive, 'expected_course_observations': COURSE_HOURS,
        'observations_in_course_range': in_course,
        'missing_course_hours': COURSE_HOURS - in_course,
        'observations_before_course_range': sum(row.timestamp < COURSE_START for row in clean),
        'observations_after_course_range': sum(row.timestamp > COURSE_END for row in clean),
        'complete_course_five_year_grid': in_course == COURSE_HOURS,
    }
    if len(clean) + len(exclusions) != counts['raw_observations']:
        raise AssertionError(f'{asset}: row accounting failed')
    return AssetData(asset, clean, summary, sorted(exclusions, key=lambda r: r['source_row']), gaps)


def calendar_years_ago(stamp: datetime, years: int) -> datetime:
    try:
        return stamp.replace(year=stamp.year - years)
    except ValueError:  # February 29 maps to February 28 in a non-leap year.
        return stamp.replace(year=stamp.year - years, day=28)


def select_window(data: AssetData, name: str) -> Window:
    """Select by observation count, or by a trailing five-calendar-year cap.

    The full-history interval is (latest close - five calendar years, latest
    close]. It caps hourly BAR LABELS to five years and does not impose a fixed
    5*8760 count. Neither experiment bridges gaps without reporting them.
    """
    rows = data.observations
    if name == 'one_year':
        enough = len(rows) >= ONE_YEAR_CLOSES
        return Window(data.asset, name, rows[-ONE_YEAR_CLOSES:] if enough else [], len(rows), enough)
    if name == 'full_history':
        lower = calendar_years_ago(rows[-1].timestamp, 5) if rows else None
        selected = [row for row in rows if row.timestamp > lower] if rows else []
        return Window(data.asset, name, selected, len(rows), len(selected) >= 2, lower)
    raise ValueError(f'Unknown window: {name}')


def export_window(window: Window, path: Path) -> None:
    def records():
        previous = None
        for index, row in enumerate(window.observations):
            elapsed = int((row.timestamp - previous) / HOUR) if previous else None
            yield {
                'observation_index': index, 'observation_label': f'P_{index}',
                'timestamp_utc': iso(row.timestamp), 'close': row.close_text,
                'source_row': row.source_row, 'elapsed_hours_from_previous': elapsed,
                'missing_hours_before': max(elapsed - 1, 0) if elapsed is not None else None,
            }
            previous = row.timestamp
    write_csv(path, ['observation_index', 'observation_label', 'timestamp_utc', 'close',
                     'source_row', 'elapsed_hours_from_previous', 'missing_hours_before'], records())


def git_read(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ['git', '-c', f'safe.directory={repo.resolve().as_posix()}', '-C', str(repo), *args],
        text=True, encoding='utf-8', errors='replace', capture_output=True, check=False,
    )
    if result.returncode:
        raise RuntimeError(f'Cannot inspect source checkout: {result.stderr.strip()}')
    return result.stdout.strip()


def acquire_snapshot(repo: Path, project: Path, reference_pdf: Path | None = None) -> dict:
    """Reuse project course data or copy an external snapshot and references.

    Existing raw bytes and an existing manifest are never overwritten. A changed
    source requires a new snapshot directory/project, not silent replacement.
    """
    repo = repo.resolve()
    project = project.resolve()
    source = repo / 'Class3' / 'data'
    local_data = project / 'data'
    if project.is_relative_to(repo) and (local_data / 'hourly').is_dir():
        source = local_data
    shared_source = source.resolve() == (project / 'data').resolve()
    supplied = sorted(p.stem for p in (source / 'hourly').glob('*USDT.csv'))
    if supplied != list(SYMBOLS):
        raise ValueError(f'Expected the 40 course assets; missing={sorted(set(SYMBOLS)-set(supplied))}; '
                         f'unexpected={sorted(set(supplied)-set(SYMBOLS))}')
    commit = git_read(repo, 'rev-parse', 'HEAD')
    dirty = git_read(repo, 'status', '--porcelain', '--', source.relative_to(repo).as_posix())
    raw = source / 'hourly' if shared_source else project / 'data' / 'raw'
    raw.mkdir(parents=True, exist_ok=True)
    manifest_path = raw.parent / 'source_manifest.json'
    previous = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else None
    if previous and previous['repository_commit'] != commit and not shared_source:
        raise ValueError('Snapshot commit differs; existing raw snapshot has been preserved.')
    entries = []
    for symbol in SYMBOLS:
        original, target = source / 'hourly' / f'{symbol}.csv', raw / f'{symbol}.csv'
        digest = sha256(original)
        if target.exists():
            if sha256(target) != digest:
                raise ValueError(f'{target}: existing raw bytes differ; refusing to overwrite.')
        else:
            shutil.copyfile(original, target)
        if sha256(target) != digest or sha256(original) != digest:
            raise RuntimeError(f'{symbol}: input changed during snapshot acquisition.')
        entries.append({'asset': symbol, 'file': target.relative_to(project).as_posix(),
                        'repository_file': original.relative_to(repo).as_posix(),
                        'bytes': target.stat().st_size, 'sha256': digest})
    references = source if shared_source else project / 'reference' / 'course_data'
    references.mkdir(parents=True, exist_ok=True)
    ref_entries = []
    for filename in ('README.md', 'fetch_sp500.py', 'build_hourly_data.py'):
        original = source / filename
        target = references / filename
        if target.exists() and sha256(target) != sha256(original):
            raise ValueError(f'{target}: existing reference differs; refusing to overwrite.')
        if not target.exists():
            shutil.copyfile(original, target)
        ref_entries.append({'file': target.relative_to(project).as_posix(), 'sha256': sha256(target)})
    pdf_info = previous.get('lab_reference') if previous else None
    if reference_pdf:
        target = project / 'reference' / 'AlgorithmsFinance_Slides3.pdf'
        if target.exists() and sha256(target) != sha256(reference_pdf):
            raise ValueError('Existing lab reference differs; refusing to overwrite.')
        if not target.exists():
            shutil.copyfile(reference_pdf, target)
        pdf_info = {'file': target.relative_to(project).as_posix(), 'sha256': sha256(target),
                    'source_file': str(reference_pdf.resolve()),
                    'lab_pdf_pages': [29, 30, 31, 32], 'data_source_pdf_page': 36}
    manifest = {
        'repository_url': REPOSITORY_URL, 'repository_commit': commit,
        'source_checkout': str(repo), 'source_data_local_changes': dirty,
        'acquired_at_utc': iso(datetime.now(UTC)), 'expected_assets': list(SYMBOLS),
        'course_expected_start_utc': iso(COURSE_START), 'course_expected_end_utc': iso(COURSE_END),
        'timestamp_semantics': 'Start-of-hour UTC label; close is the last trade within that hour.',
        'quote_currency': 'USDT', 'files': entries, 'course_references': ref_entries,
        'lab_reference': pdf_info,
    }
    if previous:
        if previous['files'] != entries:
            raise ValueError('Existing snapshot manifest differs; refusing to replace it.')
        return previous
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return manifest


def verify_snapshot(project: Path) -> dict:
    manifest = json.loads((project / 'data' / 'source_manifest.json').read_text(encoding='utf-8'))
    if sorted(item['asset'] for item in manifest['files']) != list(SYMBOLS):
        raise ValueError('Manifest does not contain exactly the 40 course assets.')
    for item in manifest['files'] + manifest['course_references']:
        path = (project / item['file']).resolve()
        if not path.is_relative_to(project.resolve()) or sha256(path) != item['sha256']:
            raise ValueError(f'Raw/reference integrity check failed: {path}')
    if manifest.get('lab_reference'):
        item = manifest['lab_reference']
        if sha256(project / item['file']) != item['sha256']:
            raise ValueError('Lab PDF integrity check failed.')
    return manifest


def make_report(manifest: dict, assets: list[dict], windows: list[dict], gaps: list[dict]) -> str:
    btc = next(row for row in assets if row['asset'] == 'BTCUSDT')
    btc_windows = [row for row in windows if row['asset'] == 'BTCUSDT']
    issues = [row for row in assets if row['excluded_rows'] or row['missing_course_hours']
              or row['ordering_violations'] or row['off_hour_timestamps']]
    insufficient_one = [r['asset'] for r in windows if r['window'] == 'one_year'
                        and not r['sufficient_observations']]
    insufficient_full = [r['asset'] for r in windows if r['window'] == 'full_history'
                         and not r['sufficient_observations']]
    incomplete = [r['asset'] for r in assets if not r['complete_course_five_year_grid']]
    lines = [
        'PRICEAMERICANPUT LAB - MARKET DATA PREPARATION',
        '',
        '1. Sources and scope',
        f'Course repository: {manifest["repository_url"]}',
        f'Commit: {manifest["repository_commit"]}',
        f'Source checkout: {manifest["source_checkout"]}',
        'The existing checkout was read only. Raw CSVs were copied byte for byte;',
        'source_manifest.json records SHA-256 hashes. Integrity was verified before',
        'and after preparation. No option prices, returns, or calibration computed.',
        'Lab reference: reference/AlgorithmsFinance_Slides3.pdf, PDF pages 29-32',
        '(printed lab slides 29/31-31/31); data sources on PDF page 36.',
        'The supplied PDF is reference material; this stage follows the user request',
        'to prepare data only. Later pricing tasks on the slides remain out of scope.',
        '',
        f'Files: {len(assets)} supplied USDT pairs; schema: timestamp_utc,close.',
        'timestamp_utc labels the START of a UTC hour; close is its last trade.',
        'Labels were retained exactly in UTC; no one-hour timestamp shift was made.',
        'The slides call these US dollars; the CSVs actually quote Tether (USDT).',
        'No USDT/USD conversion or assumption of exact dollar parity is applied.',
        'PAXGUSDT is Pax Gold per token (one fine troy ounce), not an unwrapped',
        'spot-gold or USD series. BTCUSDT is Bitcoin priced in USDT.',
        '',
        '2. Validation and cleaning policy',
        '- Audit the raw order, duplicate timestamps, invalid timestamps, off-hour',
        '  records, malformed rows, and nonnumeric/nonfinite/nonpositive prices.',
        '- Normalize timezone-aware timestamps to UTC. Exclude naive timestamps',
        '  and timestamps not aligned to the UTC hour; do not guess or round them.',
        '- Sort a separate in-memory copy. Keep the first valid observation for',
        '  an identical-price duplicate hour; exclude every valid conflicting-price',
        '  duplicate at that hour. Log every excluded row and its source line.',
        '- Never overwrite raw inputs, forward-fill, backfill, interpolate, or',
        '  create synthetic closes. Gap files list every missing interval.',
        '- Keep count sufficiency separate from equal-hour spacing. Gapped windows',
        '  remain exportable for inspection, but are NOT marked ready for the',
        '  equal-hour binomial model; a later explicit treatment is required.',
        'Raw invalid counts may overlap; excluded_rows counts distinct rows once.',
        f'Total exclusions in this snapshot: {sum(r["excluded_rows"] for r in assets):,}.',
        '',
        '3. Bitcoin validation',
        f'Raw closes: {btc["raw_observations"]:,}; usable closes: {btc["usable_observations"]:,}.',
        f'Actual coverage: {btc["start_utc"]} to {btc["end_utc"]}.',
        f'Ordering violations: {btc["ordering_violations"]}; extra duplicate rows: '
        f'{btc["duplicate_timestamp_rows"]}; invalid prices: {btc["invalid_prices"]}.',
        f'Invalid timestamps: {btc["invalid_timestamps"]}; off-hour rows: {btc["off_hour_timestamps"]}.',
        f'Internal missing hours: {btc["missing_hours"]:,} in {btc["gap_count"]:,} gaps.',
        f'Missing hours against the advertised course grid: {btc["missing_course_hours"]:,}.',
        '',
        '4. Bitcoin experiment windows',
        'One year means the last 8,761 observed valid closes, not a calendar filter.',
        'Full history uses available closes in (last close - 5 calendar years, last',
        'close]. This includes leap days and caps hourly bar labels to five years.',
        'N is observations minus one, even when elapsed time is longer due to gaps.',
    ]
    for row in btc_windows:
        lines += ['', row['window'].upper(),
                  f'  Observations: {row["observations"]:,}; N: {row["N"]}; labels: '
                  f'{row["first_label"]} ... {row["last_label"]}.',
                  f'  Start: {row["start_utc"]}; end: {row["end_utc"]}.',
                  f'  Actual elapsed duration: {row["elapsed_duration"]} '
                  f'({row["elapsed_hours"]} hours).',
                  f'  Contract: S_0 = K = P_0 = {row["P_0"]} USDT.',
                  f'  Missing hours: {row["missing_hours"]}; gap intervals: {row["gap_count"]}.',
                  f'  Consecutive hourly observations: {row["consecutive_hours"]}.',
                  f'  Data ready for hourly pricing: {row["ready_for_hourly_pricing"]}.']
    ready_btc = all(row['ready_for_hourly_pricing'] for row in btc_windows)
    lines += ['', 'Bitcoin conclusion: ' + (
        'Both windows pass the data-preparation requirements.' if ready_btc else
        'At least one window needs an explicit gap/data decision before hourly pricing.'),
        'This is data readiness only. Volatility and pricing have not been computed.',
        '', '5. All supplied assets',
        f'Advertised inclusive grid: {iso(COURSE_START)} to {iso(COURSE_END)};',
        f'{COURSE_HOURS:,} hourly closes, with {COURSE_HOURS-1:,} changes if no gaps.',
        'A count of observations is not an elapsed duration. missing_hours measures',
        'internal holes; missing_course_hours also includes absent endpoint hours.',
        f'Raw observation counts: {min(r["raw_observations"] for r in assets):,} to '
        f'{max(r["raw_observations"] for r in assets):,}.',
        f'Assets with validation or advertised-coverage issues: {len(issues)}.',
        f'Insufficient for 8,761-close experiment: {", ".join(insufficient_one) or "none"}.',
        f'Insufficient for any full-history experiment (fewer than 2 closes): '
        f'{", ".join(insufficient_full) or "none"}.',
        f'Assets missing part of the advertised five-year grid: {len(incomplete)}/40; see asset_summary.csv.',
        f'One-year windows ready for hourly pricing: '
        f'{sum(r["ready_for_hourly_pricing"] for r in windows if r["window"] == "one_year")}/40.',
        f'Full-history windows ready for hourly pricing: '
        f'{sum(r["ready_for_hourly_pricing"] for r in windows if r["window"] == "full_history")}/40.',
    ]
    grouped_gaps = defaultdict(list)
    for gap in gaps:
        grouped_gaps[(gap['first_missing_utc'], gap['last_missing_utc'], gap['missing_hours'])].append(gap['asset'])
    for (first, last, count), affected in sorted(grouped_gaps.items()):
        lines.append(f'  Missing interval {first} to {last}: {count} hour(s), '
                     f'affecting {len(set(affected))}/40 assets.')
    lines.append('Per-asset quality fields and window availability are in the two summary CSVs.')
    lines += ['', '6. S&P 500 is a separate acquisition/calendar problem',
              'The supplied data/fetch_sp500.py requests Yahoo',
              'Finance ^GSPC with range=730d&interval=1h (roughly TWO years, although',
              'the course README describes roughly three years). It drops null closes',
              'and writes hourly/SP500.csv relative to the script. It has not been run.',
              'These are index levels in points, not a USDT-quoted traded asset.',
              'Bars follow New York trading hours, with weekends, holidays, shortened',
              'sessions and daylight-saving shifts. Do not apply a 24/7 hourly missing',
              'grid or the 8,761-close criterion as one trading year; use an exchange',
              'calendar and a separate interpretation of the later contract periods.',
              'No S&P 500 data are supplied in the 40-file snapshot or mixed into its',
              'summaries. The script is documented for optional later personal use;',
              'index data should not be committed to the course repository.',
              '', '7. Outputs and reproduction',
              'asset_summary.csv: one audit/coverage row per supplied asset.',
              'window_summary.csv: both experiments, counts, elapsed time, S_0, K, status.',
              'gaps.csv: all internal missing intervals. exclusions.csv: rejected rows.',
              'windows/<ASSET>/<window>.csv: P_0 ... P_N, original source line, and',
              'elapsed_hours_from_previous/missing_hours_before to keep gaps visible.',
              'For insufficient one-year history, no partial window is labelled as a',
              'valid one-year selection; the status row reports insufficiency instead.',
              'From the project folder: python prepare_data.py',
              'Tests: python -m unittest -v test_prepare_data',
              'See README.md for acquisition and Windows interpreter instructions.', '']
    if manifest['source_data_local_changes']:
        lines.insert(9, 'WARNING: source data had local changes; exact used bytes are hashed in the manifest.')
    return '\n'.join(lines)


def prepare(project: Path, output: Path) -> tuple[list[dict], list[dict]]:
    manifest = verify_snapshot(project)
    output.mkdir(parents=True, exist_ok=True)
    asset_rows, window_rows, exclusions, gaps = [], [], [], []
    # Bitcoin is validated/exported first; the identical implementation handles all others.
    order = ['BTCUSDT'] + [symbol for symbol in SYMBOLS if symbol != 'BTCUSDT']
    source_files = {entry['asset']: entry['file'] for entry in manifest['files']}
    for symbol in order:
        data = load_asset(project / source_files[symbol])
        row = data.summary.copy()
        row['file'] = source_files[symbol]
        for name in ('one_year', 'full_history'):
            window = select_window(data, name)
            metadata = window.summary()
            path = output / 'windows' / symbol / f'{name}.csv'
            export_window(window, path)
            metadata['file'] = path.relative_to(output).as_posix()
            window_rows.append(metadata)
            row[f'{name}_sufficient_observations'] = metadata['sufficient_observations']
            row[f'{name}_ready_for_hourly_pricing'] = metadata['ready_for_hourly_pricing']
        asset_rows.append(row)
        exclusions.extend(data.exclusions)
        gaps.extend(data.gaps)
        print(f'{symbol}: {len(data.observations):,} usable; '
              f'{row["missing_hours"]:,} missing hours; {row["excluded_rows"]} excluded', flush=True)
    asset_rows.sort(key=lambda row: row['asset'])
    window_rows.sort(key=lambda row: (row['asset'], row['window']))
    write_csv(output / 'asset_summary.csv', list(asset_rows[0]), asset_rows)
    write_csv(output / 'window_summary.csv', list(window_rows[0]), window_rows)
    write_csv(output / 'exclusions.csv', ['asset', 'source_row', 'timestamp_raw', 'close_raw', 'reason'], exclusions)
    write_csv(output / 'gaps.csv', ['asset', 'previous_timestamp_utc', 'next_timestamp_utc',
              'first_missing_utc', 'last_missing_utc', 'missing_hours', 'elapsed_hours'], gaps)
    verify_snapshot(project)
    (output / 'REPORT.txt').write_text(make_report(manifest, asset_rows, window_rows, gaps), encoding='utf-8')
    (output / 'run_metadata.json').write_text(json.dumps({
        'completed_at_utc': iso(datetime.now(UTC)), 'python': sys.version,
        'repository_commit': manifest['repository_commit'], 'assets': len(asset_rows),
        'windows': len(window_rows), 'raw_hashes_verified_before_and_after': True,
        'scope': 'PriceAmericanPut market-data preparation only',
        'full_history_interval': '(latest close - 5 calendar years, latest close]',
    }, indent=2) + '\n', encoding='utf-8')
    return asset_rows, window_rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-repo', type=Path, help='Existing checkout; reuse local course data or copy an external snapshot.')
    parser.add_argument('--reference-pdf', type=Path, help='Local AlgorithmsFinance_Slides3.pdf to preserve.')
    parser.add_argument('--out', type=Path, help='Generated outputs, default: project/output.')
    args = parser.parse_args()
    project = Path(__file__).resolve().parent
    if args.source_repo:
        acquire_snapshot(args.source_repo, project, args.reference_pdf)
    elif not (project / 'data' / 'source_manifest.json').exists():
        parser.error('No raw snapshot. Pass --source-repo PATH to an existing course checkout.')
    if args.reference_pdf and not args.source_repo:
        parser.error('--reference-pdf is an acquisition option; use with --source-repo.')
    output = (args.out or project / 'output').resolve()
    protected = [project / 'data', project / 'reference']
    if any(output == path or output.is_relative_to(path) for path in protected):
        parser.error('--out cannot point inside preserved data or reference directories.')
    prepare(project, output)
    print(f'Finished. Report: {output / "REPORT.txt"}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

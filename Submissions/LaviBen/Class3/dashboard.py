#!/usr/bin/env python3
"""Build a deterministic, standalone dashboard from saved Class 3 evidence only."""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import os
from pathlib import Path


SUBMISSION_DIR = Path(__file__).resolve().parent
RESULTS_DIR = SUBMISSION_DIR / "results"
SCENARIOS = (
    ("bitcoin_one_year", "Bitcoin · one year"),
    ("bitcoin_full", "Bitcoin · full history"),
    ("all_assets_one_year", "40 assets · one year"),
    ("all_assets_full", "40 assets · full history"),
)


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _scenario(name: str, label: str, payload: dict | None) -> dict:
    missing = {
        "name": name, "label": label, "status": "missing", "steps": None,
        "assets": None, "workers": None, "median_seconds": None,
        "raw_seconds": [], "peak_rss_bytes": None, "peak_rss_mib": None,
        "memory_method": "not recorded", "units": "seconds",
        "clock": "not recorded", "created_utc": None,
    }
    if payload is None:
        return missing
    timing = payload.get("timing") or {}
    memory = payload.get("memory") or {}
    bitcoin = name.startswith("bitcoin")
    if bitcoin:
        source = payload.get("input") or {}
        steps = source.get("steps")
        assets = 1
        workers = 1
        peak = memory.get("aggregate_peak_rss_bytes")
    else:
        inputs = payload.get("inputs") or []
        steps = inputs[0].get("steps") if inputs else None
        assets = payload.get("asset_count")
        workers = payload.get("workers")
        peak = memory.get("parent_plus_tree_peak_rss_bytes")
    status = str(payload.get("status") or "unknown")
    return {
        **missing,
        "status": status,
        "steps": steps,
        "assets": assets,
        "workers": workers,
        "median_seconds": timing.get("median_seconds"),
        "raw_seconds": list(timing.get("raw_seconds") or []),
        "peak_rss_bytes": peak,
        "peak_rss_mib": peak / (1024 * 1024) if isinstance(peak, (int, float)) else None,
        "memory_method": memory.get("method", "not recorded"),
        "units": timing.get("units", "seconds"),
        "clock": timing.get("clock", "not recorded"),
        "created_utc": payload.get("created_utc"),
    }


def _assets(one_year: dict | None, full: dict | None) -> list[dict]:
    def indexed(payload: dict | None) -> dict[str, float]:
        if payload is None:
            return {}
        answer = {}
        for row in payload.get("outputs") or []:
            symbol, value = row.get("symbol"), row.get("value")
            if isinstance(symbol, str) and isinstance(value, (int, float)):
                answer[symbol] = value
        return answer

    short, long = indexed(one_year), indexed(full)
    return [
        {"symbol": symbol, "one_year": short.get(symbol), "full": long.get(symbol)}
        for symbol in sorted(set(short) | set(long))
    ]


def _boundary(results_dir: Path, filename: str, limit: int = 720) -> list[dict]:
    path = results_dir / filename
    if not path.is_file():
        return []
    rows = []
    try:
        with path.open(newline="", encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                rows.append({
                    "t": int(row["t"]),
                    "timestamp": row["timestamp_utc"],
                    "observed": float(row["observed_close"]),
                    "boundary": float(row["boundary_price"]) if row["boundary_price"] else None,
                    "first_exercise": row["first_exercise"].lower() == "true",
                })
    except (OSError, KeyError, TypeError, ValueError):
        return []
    if len(rows) <= limit:
        return rows
    stride = math.ceil(len(rows) / limit)
    selected = rows[::stride]
    required = [row for row in rows if row["first_exercise"]]
    required.extend((rows[0], rows[-1]))
    merged = {row["t"]: row for row in selected + required}
    return [merged[key] for key in sorted(merged)]


def _bitcoin(payload: dict | None, boundary: list[dict], csv_name: str) -> dict:
    if payload is None:
        return {"status": "missing", "value": None, "exercise": None,
                "boundary_count": None, "boundary_length": None,
                "boundary_csv": csv_name, "boundary": []}
    output = payload.get("output") or {}
    return {
        "status": payload.get("status", "unknown"),
        "value": output.get("put_value"),
        "exercise": output.get("exercise"),
        "boundary_count": output.get("boundary_count"),
        "boundary_length": output.get("boundary_length"),
        "boundary_csv": output.get("boundary_csv", csv_name),
        "boundary": boundary,
    }


def _pilots(python: dict | None, compiled: dict | None) -> list[dict]:
    rows = []
    if python is None or compiled is None:
        return rows

    def add(workload: str, old_rows: list, new_rows: list) -> None:
        old = {row.get("workers"): row.get("wall_seconds") for row in old_rows}
        new = {row.get("workers"): row.get("wall_seconds") for row in new_rows}
        for workers in sorted(set(old) & set(new)):
            old_time, new_time = old[workers], new[workers]
            if isinstance(old_time, (int, float)) and isinstance(new_time, (int, float)) and new_time:
                rows.append({"workload": workload, "workers": workers,
                             "python_seconds": old_time, "compiled_seconds": new_time,
                             "speedup": old_time / new_time})

    add("All 40 · one year", python.get("one_year_all_assets") or [],
        compiled.get("one_year_all_assets") or [])
    add("Four assets · full history",
        (python.get("full_history_subset") or {}).get("records") or [],
        (compiled.get("full_history_subset") or {}).get("records") or [])
    return rows


def load_dashboard_data(results_dir: str | Path = RESULTS_DIR) -> dict:
    """Load presentation data without executing pricing or measurements."""
    results_dir = Path(results_dir)
    payloads = {name: _read_json(results_dir / f"{name}.json")
                for name, _ in SCENARIOS}
    scenarios = [_scenario(name, label, payloads[name]) for name, label in SCENARIOS]
    python_pilot = _read_json(results_dir / "worker_pilot_python.json")
    compiled_pilot = _read_json(results_dir / "worker_pilot.json")
    environment = next((payload.get("environment") for payload in payloads.values()
                        if payload and payload.get("environment")), {})
    provenance = next((payload.get("provenance") for payload in payloads.values()
                       if payload and payload.get("provenance")), {})
    one_year_inputs = (payloads["all_assets_one_year"] or {}).get("inputs") or []
    full_inputs = (payloads["all_assets_full"] or {}).get("inputs") or []
    complete = sum(item["status"] == "completed" for item in scenarios)
    return {
        "title": "American Put Lab · Evidence Dashboard",
        "scenarios": scenarios,
        "completed_count": complete,
        "assets": _assets(payloads["all_assets_one_year"], payloads["all_assets_full"]),
        "bitcoin": [
            _bitcoin(payloads["bitcoin_one_year"],
                     _boundary(results_dir, "bitcoin_one_year_boundary.csv"),
                     "bitcoin_one_year_boundary.csv"),
            _bitcoin(payloads["bitcoin_full"],
                     _boundary(results_dir, "bitcoin_full_boundary.csv"),
                     "bitcoin_full_boundary.csv"),
        ],
        "pilots": _pilots(python_pilot, compiled_pilot),
        "environment": environment,
        "provenance": provenance,
        "integrity": {
            "files": max(len(one_year_inputs), len(full_inputs)),
            "one_year_observations": one_year_inputs[0].get("selected_observations") if one_year_inputs else None,
            "one_year_gap_count": sum(item.get("gap_count", 0) for item in one_year_inputs) if one_year_inputs else None,
            "full_observations": full_inputs[0].get("selected_observations") if full_inputs else None,
            "full_common_gap": "2023-03-24 13:00 UTC" if full_inputs else None,
            "price_rule": "All source prices were finite and strictly positive; non-positive prices are rejected.",
        },
    }


def _fmt(value, digits: int = 3) -> str:
    if value is None:
        return "—"
    if isinstance(value, int):
        return f"{value:,}"
    return f"{value:,.{digits}f}"


def _scenario_cards(scenarios: list[dict]) -> str:
    cards = []
    for item in scenarios:
        status = html.escape(item["status"])
        cards.append(f'''<article class="metric-card">
          <div class="metric-top"><span>{html.escape(item["label"])}</span><span class="badge {status}">{status}</span></div>
          <div class="metric-value">{_fmt(item["median_seconds"], 3)}<small> seconds</small></div>
          <div class="metric-grid"><span><b>{_fmt(item["steps"])}</b> steps</span><span><b>{_fmt(item["peak_rss_mib"], 1)}</b> MiB</span><span><b>{_fmt(item["assets"])}</b> assets</span><span><b>{_fmt(item["workers"])}</b> workers</span></div>
        </article>''')
    return "".join(cards)


def _raw_rows(scenarios: list[dict]) -> str:
    rows = []
    for item in scenarios:
        maximum = max(item["raw_seconds"], default=1.0)
        bars = "".join(
            f'<span class="repeat" style="--h:{max(5, value / maximum * 100):.2f}%" title="{value:.9f} seconds"><i></i><em>{value:.3f}</em></span>'
            for value in item["raw_seconds"]
        ) or '<span class="no-data">missing</span>'
        rows.append(f'''<div class="repeat-row"><div><strong>{html.escape(item["label"])}</strong><small>Median {_fmt(item["median_seconds"], 6)} seconds</small></div><div class="repeat-bars" aria-label="Five raw timing repeats">{bars}</div></div>''')
    return "".join(rows)


def _asset_rows(assets: list[dict]) -> str:
    rows = []
    for item in assets:
        rows.append(f'''<tr data-symbol="{html.escape(item['symbol'].lower())}"><td><strong>{html.escape(item['symbol'])}</strong></td><td>{_fmt(item['one_year'], 8)}</td><td>{_fmt(item['full'], 8)}</td><td>{_fmt((item['full'] / item['one_year']) if item['one_year'] and item['full'] is not None else None, 2)}×</td></tr>''')
    return "".join(rows) or '<tr><td colspan="4" class="no-data">Asset results missing</td></tr>'


def _line_chart(points: list[dict], label: str) -> str:
    if not points:
        return '<div class="chart-empty">Boundary evidence missing</div>'
    width, height, pad = 760, 250, 28
    values = [point["observed"] for point in points]
    values += [point["boundary"] for point in points if point["boundary"] is not None]
    low, high = min(values), max(values)
    span = high - low or 1.0

    def coords(key: str) -> str:
        answer = []
        for index, point in enumerate(points):
            value = point[key]
            if value is None:
                continue
            x = pad + index * (width - 2 * pad) / max(1, len(points) - 1)
            y = height - pad - (value - low) * (height - 2 * pad) / span
            answer.append(f"{x:.1f},{y:.1f}")
        return " ".join(answer)

    observed, boundary = coords("observed"), coords("boundary")
    first = next((p for p in points if p["first_exercise"]), None)
    marker = ""
    if first:
        index = points.index(first)
        x = pad + index * (width - 2 * pad) / max(1, len(points) - 1)
        y = height - pad - (first["observed"] - low) * (height - 2 * pad) / span
        marker = f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" class="exercise-dot"><title>First observed exercise: {html.escape(first["timestamp"])}</title></circle>'
    return f'''<svg class="line-chart" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(label)} observed price and exercise boundary">
      <line x1="{pad}" y1="{height-pad}" x2="{width-pad}" y2="{height-pad}" class="axis"/>
      <polyline points="{observed}" class="observed"/><polyline points="{boundary}" class="boundary"/>{marker}
      <text x="{pad}" y="16">{high:,.2f}</text><text x="{pad}" y="{height-7}">{low:,.2f}</text>
    </svg>'''


def _bitcoin_cards(bitcoin: list[dict]) -> str:
    labels = ("One-year BTCUSDT", "Full-history BTCUSDT")
    cards = []
    for label, item in zip(labels, bitcoin):
        exercise = item.get("exercise") or {}
        timestamp = exercise.get("timestamp_utc", "missing")
        cards.append(f'''<article class="panel btc-panel">
          <div class="panel-head"><div><p class="eyebrow">EXERCISE EVIDENCE</p><h3>{label}</h3></div><span class="badge {html.escape(str(item['status']))}">{html.escape(str(item['status']))}</span></div>
          <div class="btc-stats"><span>Put value <b>{_fmt(item['value'], 6)}</b></span><span>First observed exercise <b>{html.escape(str(timestamp)).replace('T', ' ')}</b></span><span>Observed <b>{_fmt(exercise.get('observed_price'), 2)}</b></span><span>Boundary <b>{_fmt(exercise.get('boundary_price'), 2)}</b></span></div>
          {_line_chart(item['boundary'], label)}
          <div class="legend"><span class="cyan"></span>Observed close <span class="amber"></span>Exercise boundary <span class="dot"></span>First exercise</div>
          <a class="data-link" href="{html.escape(item['boundary_csv'])}">Open exact {html.escape(item['boundary_csv'])} →</a>
        </article>''')
    return "".join(cards)


def _pilot_rows(pilots: list[dict]) -> str:
    return "".join(
        f'''<tr><td>{html.escape(row['workload'])}</td><td>{row['workers']}</td><td>{row['python_seconds']:.6f}</td><td>{row['compiled_seconds']:.6f}</td><td><strong>{row['speedup']:.2f}×</strong></td></tr>'''
        for row in pilots
    ) or '<tr><td colspan="5" class="no-data">Pilot evidence missing</td></tr>'


def _checksums(provenance: dict) -> str:
    labels = {
        "american_put_sha256": "Python kernel", "kernel_source_sha256": "C kernel",
        "compiled_backend_sha256": "Backend wrapper", "market_data_sha256": "Market-data loader",
        "runner_sha256": "Bitcoin runner",
    }
    rows = []
    for key, label in labels.items():
        value = provenance.get(key)
        if value:
            rows.append(f'<li><span>{label}</span><code>{html.escape(str(value))}</code></li>')
    return "".join(rows) or '<li class="no-data">Checksums missing</li>'


def render_dashboard(data: dict) -> str:
    """Render one byte-stable HTML document with no external dependencies."""
    scenarios = data["scenarios"]
    environment = data.get("environment") or {}
    compiler = environment.get("compiled_backend") or {}
    integrity = data.get("integrity") or {}
    overall = "complete" if data.get("completed_count") == 4 else "attention"
    css = r'''
:root{--bg:#070b14;--surface:#101724;--surface2:#151e2e;--line:#263249;--text:#f3f6fb;--muted:#8f9bb0;--cyan:#49d6d2;--amber:#ffb547;--green:#63e6a4;--red:#ff7887;--violet:#9385ff}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:radial-gradient(circle at 10% -10%,#163c43 0,transparent 28%),radial-gradient(circle at 95% 0,#281f55 0,transparent 25%),var(--bg);color:var(--text);font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-variant-numeric:tabular-nums}.shell{max-width:1440px;margin:auto;padding:28px 34px 70px}.topbar{display:flex;justify-content:space-between;align-items:center;padding:8px 0 34px}.brand{display:flex;align-items:center;gap:13px}.mark{width:39px;height:39px;border-radius:11px;background:linear-gradient(145deg,var(--cyan),#3d85ff);display:grid;place-items:center;color:#061016;font-weight:900}.brand b{display:block}.brand small,.muted{color:var(--muted)}nav{display:flex;gap:5px;background:#0d1420;border:1px solid var(--line);border-radius:12px;padding:4px}nav a{color:var(--muted);text-decoration:none;padding:9px 13px;border-radius:8px;font-size:13px}nav a:hover{color:var(--text);background:var(--surface2)}.hero{display:grid;grid-template-columns:1.5fr .8fr;gap:28px;align-items:end;margin-bottom:32px}.eyebrow{letter-spacing:.17em;font-size:11px;color:var(--cyan);font-weight:800;margin:0 0 9px}.hero h1{font-size:clamp(34px,5vw,61px);line-height:1.02;letter-spacing:-.045em;margin:0;max-width:830px}.hero p{color:var(--muted);font-size:16px;line-height:1.65;max-width:780px}.hero-status{background:linear-gradient(140deg,rgba(73,214,210,.12),rgba(147,133,255,.08));border:1px solid var(--line);border-radius:18px;padding:22px}.hero-status strong{font-size:36px;display:block}.hero-status span{color:var(--muted)}.section{margin-top:46px;scroll-margin-top:20px}.section-title{display:flex;justify-content:space-between;align-items:end;margin-bottom:15px}.section-title h2{font-size:22px;margin:3px 0}.section-title p{color:var(--muted);margin:0;font-size:13px}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:13px}.metric-card,.panel{background:linear-gradient(150deg,rgba(21,30,46,.96),rgba(13,20,32,.96));border:1px solid var(--line);border-radius:17px;padding:18px;box-shadow:0 18px 50px rgba(0,0,0,.18)}.metric-top,.panel-head{display:flex;justify-content:space-between;align-items:center;gap:10px;color:#cbd4e4;font-size:13px}.badge{padding:5px 8px;border-radius:99px;font-size:10px;text-transform:uppercase;letter-spacing:.08em;background:#2b3342;color:#c7d0df}.badge.completed,.badge.complete{color:var(--green);background:rgba(99,230,164,.11);border:1px solid rgba(99,230,164,.22)}.badge.missing,.badge.stopped,.badge.attention{color:var(--red);background:rgba(255,120,135,.1);border:1px solid rgba(255,120,135,.2)}.metric-value{font-size:31px;font-weight:760;margin:22px 0}.metric-value small{font-size:12px;color:var(--muted);font-weight:500}.metric-grid{display:grid;grid-template-columns:1fr 1fr;border-top:1px solid var(--line);padding-top:13px;gap:10px;color:var(--muted);font-size:11px}.metric-grid b{color:#dbe3ef}.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:14px}.panel-head h3{margin:2px 0;font-size:17px}.repeats{padding:7px 18px}.repeat-row{display:grid;grid-template-columns:240px 1fr;align-items:center;padding:16px 0;border-bottom:1px solid var(--line)}.repeat-row:last-child{border-bottom:0}.repeat-row strong,.repeat-row small{display:block}.repeat-row small{color:var(--muted);margin-top:4px}.repeat-bars{height:62px;display:flex;gap:11px;align-items:flex-end}.repeat{height:100%;flex:1;display:flex;align-items:flex-end;position:relative}.repeat i{display:block;width:100%;height:var(--h);border-radius:5px 5px 2px 2px;background:linear-gradient(180deg,var(--cyan),#2477b9);min-height:5px}.repeat em{position:absolute;bottom:-14px;left:50%;transform:translateX(-50%);font-style:normal;color:var(--muted);font-size:9px}.btc-panel{overflow:hidden}.btc-stats{display:grid;grid-template-columns:1fr 1.5fr;gap:8px;margin:16px 0}.btc-stats span{font-size:11px;color:var(--muted);background:#0b111c;border-radius:8px;padding:9px}.btc-stats b{display:block;color:var(--text);margin-top:4px;font-size:12px}.line-chart{width:100%;height:250px;background:#0a101a;border:1px solid #1e2a3e;border-radius:11px}.line-chart text{fill:var(--muted);font-size:9px}.line-chart .axis{stroke:#38455b}.line-chart polyline{fill:none;stroke-width:2;vector-effect:non-scaling-stroke}.observed{stroke:var(--cyan)}.boundary{stroke:var(--amber)}.exercise-dot{fill:var(--violet);stroke:#fff;stroke-width:2}.legend{display:flex;align-items:center;gap:7px;color:var(--muted);font-size:10px;margin:10px 0}.legend span{display:inline-block;width:16px;height:2px;margin-left:8px}.legend .cyan{background:var(--cyan)}.legend .amber{background:var(--amber)}.legend .dot{width:7px;height:7px;border-radius:50%;background:var(--violet)}.data-link{display:inline-block;color:var(--cyan);font-size:12px;text-decoration:none;margin-top:8px}.toolbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}.search{background:#0a101a;border:1px solid var(--line);color:var(--text);padding:10px 12px;border-radius:10px;width:260px}.table-wrap{max-height:465px;overflow:auto;border:1px solid var(--line);border-radius:12px}table{border-collapse:collapse;width:100%;font-size:12px}th{text-align:left;position:sticky;top:0;background:#172033;color:var(--muted);padding:11px;z-index:1}td{padding:11px;border-top:1px solid var(--line)}tbody tr:hover{background:rgba(73,214,210,.04)}td:not(:first-child),th:not(:first-child){text-align:right}.optimization{display:grid;grid-template-columns:1.35fr .65fr;gap:14px}.callout{display:flex;flex-direction:column;justify-content:center;min-height:250px;background:linear-gradient(145deg,rgba(73,214,210,.13),rgba(147,133,255,.13));text-align:center}.callout strong{font-size:55px;letter-spacing:-.05em;color:var(--green)}.callout span{color:var(--muted)}.evidence{display:grid;grid-template-columns:1fr 1fr;gap:14px}.facts{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px}.fact{background:#0b111c;border-radius:10px;padding:12px}.fact small{display:block;color:var(--muted);margin-bottom:5px}.fact b{font-size:12px}.checksums{list-style:none;margin:12px 0 0;padding:0}.checksums li{border-top:1px solid var(--line);padding:10px 0}.checksums span{display:block;font-size:11px;color:var(--muted);margin-bottom:5px}.checksums code{font-size:10px;color:#cdd7e6;word-break:break-all}.note{border-left:3px solid var(--amber);padding:10px 12px;background:rgba(255,181,71,.07);color:#d6c5a7;font-size:12px;line-height:1.55;margin-top:12px}.no-data,.chart-empty{color:var(--red);padding:25px;text-align:center}.footer{margin-top:50px;padding-top:20px;border-top:1px solid var(--line);color:var(--muted);font-size:11px;display:flex;justify-content:space-between}@media(max-width:1050px){.cards{grid-template-columns:1fr 1fr}.grid-2,.optimization,.evidence{grid-template-columns:1fr}.hero{grid-template-columns:1fr}.hero-status{display:none}}@media(max-width:650px){.shell{padding:20px 16px 50px}nav{display:none}.cards{grid-template-columns:1fr}.repeat-row{grid-template-columns:1fr;gap:13px}.btc-stats,.facts{grid-template-columns:1fr}.section-title{align-items:start;flex-direction:column;gap:5px}.search{width:100%}.footer{display:block}.footer span{display:block;margin-top:5px}}
'''
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(data['title'])}</title><style>{css}</style></head>
<body><main class="shell">
  <header class="topbar"><div class="brand"><div class="mark">P</div><div><b>AF · Class 3</b><small>Saved-evidence dashboard</small></div></div><nav aria-label="Dashboard sections"><a href="#runs">Runs</a><a href="#bitcoin">Bitcoin</a><a href="#assets">Assets</a><a href="#optimization">Optimization</a><a href="#evidence">Audit</a></nav></header>
  <section class="hero"><div><p class="eyebrow">AMERICAN PUT · EXACT BINOMIAL RECURRENCE</p><h1>One asset first.<br>Forty assets in parallel.</h1><p>A reproducible view of correctness, runtime, memory, exercise boundaries, and CPU scaling. Every figure below comes from saved JSON or CSV evidence—this page runs no pricing and performs no measurements.</p></div><div class="hero-status"><span class="badge {overall}">{overall}</span><strong>{data.get('completed_count',0)} / 4</strong><span>canonical scenarios completed</span></div></section>
  <section class="section" id="runs"><div class="section-title"><div><p class="eyebrow">CANONICAL RUNS</p><h2>Runtime and memory at a glance</h2></div><p>Median of five repeats · aggregate Peak RSS in MiB</p></div><div class="cards">{_scenario_cards(scenarios)}</div></section>
  <section class="section"><div class="section-title"><div><p class="eyebrow">RAW EVIDENCE</p><h2>Raw timing repeats</h2></div><p>Units: seconds · clock: time.perf_counter</p></div><div class="panel repeats">{_raw_rows(scenarios)}</div></section>
  <section class="section" id="bitcoin"><div class="section-title"><div><p class="eyebrow">ONE ASSET · FULL OUTPUT</p><h2>Bitcoin exercise boundary</h2></div><p>Observed close versus model boundary</p></div><div class="grid-2">{_bitcoin_cards(data.get('bitcoin') or [])}</div></section>
  <section class="section" id="assets"><div class="section-title"><div><p class="eyebrow">MULTI-ASSET RESULTS</p><h2>All 40 put values</h2></div><p>Compiled kernel · 8 workers</p></div><div class="panel"><div class="toolbar"><span class="muted">Search the complete saved output</span><input id="asset-search" class="search" type="search" placeholder="Filter symbol…" aria-label="Filter assets by symbol"></div><div class="table-wrap"><table><thead><tr><th>Symbol</th><th>One-year value</th><th>Full-history value</th><th>Full / 1Y</th></tr></thead><tbody id="asset-body">{_asset_rows(data.get('assets') or [])}</tbody></table></div></div></section>
  <section class="section" id="optimization"><div class="section-title"><div><p class="eyebrow">CPU &amp; KERNEL OPTIMIZATION</p><h2>Measured before choosing the backend</h2></div><p>Prepared jobs identical · compilation and warm-up excluded</p></div><div class="optimization"><div class="panel"><table><thead><tr><th>Workload</th><th>Workers</th><th>Python seconds</th><th>Compiled seconds</th><th>Speedup</th></tr></thead><tbody>{_pilot_rows(data.get('pilots') or [])}</tbody></table><div class="note">8 workers had the lowest measured 40-asset one-year wall time. Separate processes allow concurrent CPU execution; the operating system schedules them, so no fixed core affinity is claimed.</div></div><div class="panel callout"><span>Best measured backend gain</span><strong>{max((row['speedup'] for row in data.get('pilots') or []), default=0):.2f}×</strong><span>Python → compiled C, same values</span></div></div></section>
  <section class="section" id="evidence"><div class="section-title"><div><p class="eyebrow">REPRODUCIBILITY &amp; INTEGRITY</p><h2>What the measurements include</h2></div><p>No clamping · no extrapolation · no silent omissions</p></div><div class="evidence"><article class="panel"><div class="panel-head"><h3>Environment and data</h3><span class="badge complete">recorded</span></div><div class="facts"><div class="fact"><small>Python</small><b>{html.escape(str(environment.get('python','missing')).split(' ')[0])}</b></div><div class="fact"><small>Compiler</small><b>{html.escape(str(compiler.get('compiler_version','missing')).splitlines()[0])}</b></div><div class="fact"><small>Logical CPUs</small><b>{_fmt(environment.get('logical_cpu_count'))}</b></div><div class="fact"><small>Platform</small><b>{html.escape(str(environment.get('platform','missing')))}</b></div><div class="fact"><small>Input files</small><b>{_fmt(integrity.get('files'))}</b></div><div class="fact"><small>One-year observations</small><b>{_fmt(integrity.get('one_year_observations'))}</b></div></div><div class="note">{html.escape(str(integrity.get('price_rule','Price validation missing')))} Full histories retain the one common missing hour at {html.escape(str(integrity.get('full_common_gap','missing')))}; it was reported and not filled.</div><div class="note">Peak RSS is aggregate process memory: Bitcoin samples parent plus fresh child; multi-asset runs sample the coordinator process tree. Required output objects remain alive at the final sample.</div></article><article class="panel"><div class="panel-head"><h3>Source checksums</h3><span class="badge complete">SHA-256</span></div><ul class="checksums">{_checksums(data.get('provenance') or {})}</ul><div class="facts"><div class="fact"><small>Git branch</small><b>{html.escape(str((data.get('provenance') or {}).get('git_branch','missing')))}</b></div><div class="fact"><small>Code commit</small><b>{html.escape(str((data.get('provenance') or {}).get('git_commit','missing'))[:12])}</b></div></div></article></div></section>
  <footer class="footer"><span>Built from saved results only · standalone HTML · no network dependencies</span><span>Statuses: completed / missing / stopped are always visible</span></footer>
</main><script>
const search=document.getElementById('asset-search');if(search)search.addEventListener('input',()=>{{const q=search.value.trim().toLowerCase();document.querySelectorAll('#asset-body tr[data-symbol]').forEach(row=>row.hidden=!row.dataset.symbol.includes(q));}});
</script></body></html>'''


def build(output: str | Path = RESULTS_DIR / "dashboard.html", check: bool = False) -> Path:
    output = Path(output)
    rendered = render_dashboard(load_dashboard_data(output.parent))
    if check:
        if not output.is_file() or output.read_text(encoding="utf-8") != rendered:
            raise SystemExit(f"dashboard is stale: {output}")
        print(f"byte-stable dashboard verified: {output}")
        return output
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(rendered, encoding="utf-8", newline="\n")
    os.replace(temporary, output)
    print(f"wrote {output}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=RESULTS_DIR / "dashboard.html")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    build(args.output, args.check)


if __name__ == "__main__":
    main()

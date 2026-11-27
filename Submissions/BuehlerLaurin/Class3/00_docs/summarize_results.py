"""Render README/report tables from completed saved CSVs, no repricing."""
import csv
import json
import math
from pathlib import Path


def read(path):
    with path.open(newline='',encoding='utf-8') as f:
        return list(csv.DictReader(f))


def main():
    root=Path.cwd(); relative=Path((root/'03_results/LATEST.txt').read_text(encoding='utf-8').strip()); d=root/relative
    summary=read(d/'summary.csv'); assert len(summary)==5
    for row in summary:
        if row['version']=='A':
            row['successful_assets']=row['assets']; row['failed_assets']='0'
        else:
            details=read(d/(row['workload']+'_B_assets.csv'))
            row['successful_assets']=str(sum(r['status']=='ok' for r in details))
            row['failed_assets']=str(sum(r['status']!='ok' for r in details))
    with (d/'summary.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(summary[0])); writer.writeheader(); writer.writerows(summary)
    table=['| Workload | Version | N | Assets | Median seconds | Whole-run peak bytes | Pricing peak bytes |',
           '|---|---|---:|---:|---:|---:|---:|']
    for r in summary:
        table.append(f'| {r["workload"]} | {r["version"]} | {r["N"]} | {r["assets"]} | {float(r["seconds"]):.6f} | {r["peak_bytes"] or "not measured"} | {r["pricing_peak_bytes"] or "not measured"} |')
    a=next(float(r['seconds']) for r in summary if r['workload']=='BTC1y' and r['version']=='A')
    b=next(float(r['seconds']) for r in summary if r['workload']=='BTC1y' and r['version']=='B')
    growth=read(d/'growth.csv'); assert len(growth)==8
    gtable=['| Version | N | Status | Median seconds |','|---|---:|---|---:|']
    slopes={}
    for version in ['A','B']:
        done=[r for r in growth if r['version']==version and r['status']=='ok']
        if len(done)>=3:
            xs=[math.log(int(r['N'])) for r in done]; ys=[math.log(float(r['seconds'])) for r in done]
            mx=sum(xs)/len(xs); my=sum(ys)/len(ys)
            slopes[version]=sum((x-mx)*(y-my) for x,y in zip(xs,ys))/sum((x-mx)**2 for x in xs)
    for r in growth:
        seconds=f'{float(r["seconds"]):.6f}' if r['seconds'] else '—'
        gtable.append(f'| {r["version"]} | {r["N"]} | {r["status"]} | {seconds} |')
    btc=[]
    for workload in ['BTC1y','BTC5y']:
        r=read(d/(workload+'_B_assets.csv'))[0]
        btc.append(f'- {workload}: value **{float(r["value"]):.10f} USDT**; first exercise **{r["exercise_utc"] or "never"}**, payoff **{float(r["payoff"]):.2f} USDT**.' if r['payoff'] else f'- {workload}: value {r["value"]} USDT; never exercised.')
    result_section='\n'.join(table)+f'\n\nBTC1y A/B median ratio: **{a/b:.2f}×** on these inputs and this machine. A timing is reused from the earlier same-machine run after A/data/common/pipeline hash checks. Both run folders and reuse provenance are retained.\n\n'+'\n'.join(btc)+'\n\n'+'\n'.join(gtable)+'\n\n'
    result_section+='Log-log least-squares slopes over completed growth cells: '+', '.join(f'{k}={v:.3f}' for k,v in slopes.items())+'. '
    result_section+='These are finite-range scaling observations, not complexity proofs. A visits quadratic nodes in Python; B has the same node count but layer overhead can dominate the 1k–8k range. Stopped cells are excluded from slopes and ratios; their 60 s limit covers the complete child process, not one repeat.\n'
    (d/'RESULTS_TABLE.md').write_text(result_section,encoding='utf-8')
    (d/'growth_fit.json').write_text(json.dumps(slopes,indent=2)+'\n',encoding='utf-8')
    readme=f'''# Class 3 Lab 2 — Laurin Bühler
FIN71055 American put pricing. Blocks 1–2 complete; stopped for review before independent audit/hand-off.

Two tested versions: A transparent pure Python, B NumPy layer induction with an O(N) CRR stock/payoff lattice. Both compute the boundary during backward induction without a stored tree. See [SPEC.md](SPEC.md), [REPORT](00_docs/REPORT.md), [TRACE](00_docs/TRACE.md) and [requirements map](00_docs/REQUIREMENTS_MAP.md).

## Results
Saved run: [{relative.as_posix()}]({relative.as_posix()}/summary.csv).

{result_section}
## Measurement scope
One untimed warm-up, five timing repeats, median and all raw repeats. Whole-run seconds include file loading, calibration, pricing, boundary extraction and observed first-exercise search. Imports/process startup and CSV serialization excluded; warm caches expected. Forty assets run sequentially in one process per batch, with compact scalar summaries retained.

Tracemalloc runs separately from timing. Primary peak covers the whole run. Secondary covers an isolated pricing call, including returned boundary, with calibrated inputs pre-existing; for a batch the table shows the maximum of separately measured calls. These are traced bytes, not RSS. A is timing-only for the ratio. Phase instrumentation is a separate run, with parse and calibration reported together.

All 40 supplied files contain 43,823 observed closes (N=43,822) and one missing hour. Last year selects the last 8,761 rows (N=8,760), not a calendar filter. Read-only originals: ../../../Class3/data/hourly. [Local hashes](06_data/supplied/MANIFEST.json) establish snapshot consistency only, not upstream authentication. No S&P 500 download.

## Saved artifacts
The run contains summary.csv (including success/error counts), timing.csv and per-cell raw repeats, memory.csv with scopes, phase_instrumentation.csv, growth.csv/logs, env.json, source_sha256.json, tests.txt, per-workload asset CSVs, and one full boundary/path CSV per asset/window. Missing boundaries are empty CSV fields; Python uses None and JSON null. Final comparison exceptions are explicitly recorded in BTC1y_A_B_FINAL_COMPARISON.json. GROWTH_PROTOCOL.txt identifies the direct-interpreter final grid; the initial launcher grid is retained separately and excluded from final tables.

## Run commands (PowerShell, from this folder)
Use the existing venv. No installs were performed; requirements.txt pins the verified environment.

```powershell
$env:TEMP=Join-Path (Get-Location) 'scratch'
$env:TMP=$env:TEMP
$env:HYPOTHESIS_STORAGE_DIRECTORY=Join-Path (Get-Location) '.hypothesis'
& "$env:USERPROFILE/.venvs/aif-class3/Scripts/python.exe" -B evidence.py tests -- "$env:USERPROFILE/.venvs/aif-class3/Scripts/python.exe" -B -m pytest -q --basetemp=scratch/pytest-manual
& "$env:USERPROFILE/.venvs/aif-class3/Scripts/python.exe" -B evidence.py data -- "$env:USERPROFILE/.venvs/aif-class3/Scripts/python.exe" -B verify_manifest.py 06_data/supplied --metadata
& "$env:USERPROFILE/.venvs/aif-class3/Scripts/python.exe" -B evidence.py diagnostic -- "$env:USERPROFILE/.venvs/aif-class3/Scripts/python.exe" -B run.py bench.diagnostic
$env:EVIDENCE_TIMEOUT_S='14400'
& "$env:USERPROFILE/.venvs/aif-class3/Scripts/python.exe" -B evidence.py benchmark -- "$env:USERPROFILE/.venvs/aif-class3/Scripts/python.exe" -u -B run.py bench.run_lab
& "$env:USERPROFILE/.venvs/aif-class3/Scripts/python.exe" -B evidence.py artifacts -- "$env:USERPROFILE/.venvs/aif-class3/Scripts/python.exe" -B 00_docs/verify_results.py
```
Before running tests, keep TEMP/TMP and Hypothesis storage inside this exercise as recorded in the evidence commands. Full benchmark regeneration is expensive. The reported run's exact command uses --reuse-a with provenance recorded inside its run folder. The verifier's independent baseline comparison intentionally references the preserved initial run.

## Evidence and limits
Saved red before A/data; A green before B; B/pipeline red before implementation; shared green contracts, exact Fraction oracle through N=12, six mutants and 200 Hypothesis comparisons; full BTC1y A/B differential and revised artifact verification. See [evidence index](05_evidence/INDEX.md).

Slide quotations are Laurin's transcription; PDF not independently extracted. Stable stock construction and affine continuation are documented deviations in evaluation, preserving the recurrence and exact exercise rule. Claude's e^-657 underflow illustration was corrected by Codex (normal/subnormal transition near e^-708; zero near e^-745).

These are human-commit-plus-dirty-source-hash measurements, not clean-commit or fresh-environment reproducibility claims. The interrupted initial B grid remains explicitly labelled and incomplete cells are excluded. Independent Claude audit/attack and fresh-environment hand-off verification remain pending. No git writes, installs or network calls.
'''
    (root/'README.md').write_text(readme,encoding='utf-8')
    report=root/'00_docs/REPORT.md'; text=report.read_text(encoding='utf-8')
    marker='Final tables and growth interpretation are generated from saved CSVs in the final run folder after the grid completes. No extrapolation replaces stopped or missing measurements.'
    assert marker in text
    report.write_text(text.replace(marker,result_section+'\nSaved run: '+relative.as_posix()),encoding='utf-8')
    print('README/report tables generated from '+str(relative))
    print(f'BTC1y A/B median ratio: {a/b:.6f}')
    print('Growth fitted exponents: '+json.dumps(slopes))


if __name__=='__main__':
    main()

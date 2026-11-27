param(
    [string]$Session = 'phase4_b3r_fast_20261122',
    [string]$Reference = '03_results/runs/20261122T130145Z_00bb1ad_phase4_b3r_20261122',
    [switch]$AllowLong,
    [switch]$PlanOnly
)
if (-not $PlanOnly -and -not $AllowLong) { throw 'Explicit -AllowLong required; checkpoint permits plan only.' }
$fastPython = Join-Path $env:USERPROFILE '.venvs\aif-a1\Scripts\python.exe'
$fastGates = '05_evidence/b3r_fast_correctness.json'
Write-Output "Reference B3r: $Reference; new session: $Session"
Write-Output 'Rule: all correctness gates; fast/B3r geometric mean <=0.90 at official100k; every matched replay ratio <=1.05.'
if (-not $PlanOnly) {
    & $fastPython run.py bench.assess_fast verify-gates $fastGates
    if ($LASTEXITCODE -ne 0) { throw 'Fresh matching correctness evidence required before measuring.' }
}
foreach ($fastPart in @('official','post_attack')) {
    $fastArgs = @('run.py','bench.run_all','--part',$fastPart,'--versions','B3r_fast',
        '--session',$Session,'--manifest','06_data/generated/post_attack/manifest.json','--skip-after-stop')
    if ($PlanOnly) { $fastArgs += '--plan-only' } else { $fastArgs += '--allow-long' }
    & $fastPython @fastArgs
    if ($LASTEXITCODE -ne 0) { throw 'Benchmark pipeline failed; inspect evidence before continuing.' }
}
if (-not $PlanOnly) {
    $fastPointer = Get-Content -LiteralPath (Join-Path 'scratch' "bench_session_$Session.json") -Raw | ConvertFrom-Json
    & $fastPython run.py bench.assess_fast compare $Reference $fastPointer.run_dir --gates $fastGates
    if ($LASTEXITCODE -ne 0) { throw 'Saved-result comparison failed.' }
}

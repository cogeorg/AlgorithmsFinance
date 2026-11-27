param([switch]$AllowLong,[switch]$PlanOnly)
if (-not $PlanOnly -and -not $AllowLong) { throw 'Explicit -AllowLong required for the ONE binding attempt.' }
$rematchPython = Join-Path $env:USERPROFILE '.venvs\aif-a1\Scripts\python.exe'
$rematchSession = 'phase4_b3r_fast_rematch_20261122'
Write-Output 'ONE binding attempt; B3r/B3r_fast, same-session timing only; alternate version order by case.'
if (-not $PlanOnly) {
    & $rematchPython run.py bench.assess_rematch claim
    if ($LASTEXITCODE -ne 0) { throw 'Rematch preflight/claim failed. No measurement started.' }
}
$rematchJobs = @(@{Part='official';Offset=0},@{Part='post_attack';Offset=45})
foreach ($rematchJob in $rematchJobs) {
    $rematchArgs = @('run.py','bench.run_all','--part',$rematchJob.Part,'--versions','B3r,B3r_fast',
        '--modes','timing','--session',$rematchSession,'--manifest','06_data/generated/post_attack/manifest.json',
        '--interleave','--interleave-offset',$rematchJob.Offset.ToString())
    if ($PlanOnly) { $rematchArgs += '--plan-only' } else { $rematchArgs += '--allow-long' }
    & $rematchPython @rematchArgs
    if ($LASTEXITCODE -ne 0) {
        if ($PlanOnly) { throw 'Plan preview failed.' }
        Write-Output 'Pipeline failed; partial attempt will be assessed as binding, with no retry.'
        break
    }
}
if (-not $PlanOnly) {
    $rematchPointerPath = Join-Path 'scratch' "bench_session_$rematchSession.json"
    $rematchDirectory = 'scratch/b3r_fast_rematch_no_run'
    if (Test-Path -LiteralPath $rematchPointerPath) {
        $rematchPointer = Get-Content -LiteralPath $rematchPointerPath -Raw | ConvertFrom-Json
        $rematchDirectory = $rematchPointer.run_dir
    }
    & $rematchPython run.py bench.assess_rematch assess $rematchDirectory
    if ($LASTEXITCODE -ne 0) { throw 'Assessment failed; attempt is still consumed. Preserve files; do not rerun measurement.' }
}

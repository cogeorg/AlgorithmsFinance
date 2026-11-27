param(
    [string]$Session = 'phase4_b3r_20261122',
    [switch]$AllowLong,
    [switch]$PlanOnly
)
if (-not $PlanOnly -and -not $AllowLong) { throw 'Explicit -AllowLong required; this command may run overnight.' }
$revisionPython = Join-Path $env:USERPROFILE '.venvs\aif-a1\Scripts\python.exe'
$revisionManifest = '06_data/generated/post_attack/manifest.json'
if (-not $PlanOnly) {
    # Data preparation/hash verification precede every measurement worker.
    & $revisionPython run.py bench.catalog --post-attack
    if ($LASTEXITCODE -ne 0) { throw 'Post-attack data preparation failed.' }
}
$revisionParts = @('official','million','queue','liquidation','adversarial','churn','post_attack')
$revisionJobs = @()
foreach ($revisionPart in $revisionParts) {
    $revisionJobs += @{Part=$revisionPart;Versions='B3r'}
}
$revisionJobs += @{Part='post_attack';Versions='B1,B2,B3'}
foreach ($revisionPart in $revisionParts) {
    $revisionJobs += @{Part=$revisionPart;Versions='A'}
}
foreach ($revisionJob in $revisionJobs) {
    # Laurin's declared baseline scope, fixed 2026-11-22 before A measurements.
    $revisionMaxSize = 1000000
    if ($revisionJob.Versions -eq 'A' -and $revisionJob.Part -notin @('official','million')) {
        $revisionMaxSize = 10000
    }
    $revisionArgs = @('run.py','bench.run_all','--part',$revisionJob.Part,
        '--versions',$revisionJob.Versions,'--session',$Session,'--manifest',$revisionManifest,
        '--baseline-protocol','single-large','--skip-after-stop','--max-size',$revisionMaxSize.ToString())
    if ($PlanOnly) { $revisionArgs += '--plan-only' } else { $revisionArgs += '--allow-long' }
    & $revisionPython @revisionArgs
    if ($LASTEXITCODE -ne 0) { throw 'Revision batch failed; inspect the saved records before continuing.' }
}

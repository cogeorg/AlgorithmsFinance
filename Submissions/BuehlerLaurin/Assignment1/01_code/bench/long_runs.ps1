param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('official','million','queue','liquidation','adversarial','churn')]
    [string]$Part,
    [string]$Session = 'phase4',
    [switch]$AllowLong,
    [switch]$CandidatesOnly,
    [switch]$BaselineOnly,
    [ValidateSet(1000,10000,100000,1000000)]
    [int]$MaxSize = 1000000
)
if (-not $AllowLong) { throw 'Long runs require the explicit -AllowLong switch. Phase 4a runs smoke only.' }
if ($CandidatesOnly -and $BaselineOnly) { throw 'Choose CandidatesOnly or BaselineOnly, not both.' }
$benchmarkPython = Join-Path $env:USERPROFILE '.venvs\aif-a1\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $benchmarkPython)) { throw 'Use the existing aif-a1 venv from README.md.' }
# Complete all candidate measurements first; the slow baseline is a separate batch.
$benchmarkArguments = @('run.py','bench.run_all','--part',$Part,'--allow-long','--session',$Session,
                        '--max-size',$MaxSize.ToString(),'--skip-after-stop',
                        '--baseline-protocol','single-large')
if (-not $BaselineOnly) {
    & $benchmarkPython @benchmarkArguments --versions 'B1,B2,B3'
    if ($LASTEXITCODE -ne 0) { throw 'Candidate batch failed; inspect saved cells/logs before continuing.' }
}
if (-not $CandidatesOnly) {
    Write-Output 'Declared deviation (2026-11-22): A at 100k/1M has one measured trial, no warm-up; report A: single trial. A at 1k/10k and all B candidates retain warm-up + 5 repeats.'
    & $benchmarkPython @benchmarkArguments --versions 'A'
    if ($LASTEXITCODE -ne 0) { throw 'Baseline batch failed; inspect saved cells/logs.' }
}

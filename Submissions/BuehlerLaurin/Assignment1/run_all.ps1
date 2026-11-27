param([switch]$Full,[switch]$NoDashboard)
$ErrorActionPreference = 'Stop'
$step = 'enter Assignment1'
Push-Location $PSScriptRoot
try {
    # 1. First use only: create a local environment and install the pinned packages.
    $step = 'create/install .venv'
    if (-not (Test-Path -LiteralPath '.venv')) {
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'python -m venv failed' }
        & ./.venv/Scripts/python.exe -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) { throw 'pip install failed; inspect/remove an incomplete .venv manually before retrying' }
    } else { Write-Output 'SKIP install: .venv exists' }
    if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) { throw '.venv has no Windows Python' }
    $savedReproductionPath = $env:PATH
    $env:PATH = (Join-Path $PSScriptRoot '.venv/Scripts') + [IO.Path]::PathSeparator + $env:PATH
    New-Item -ItemType Directory -Force -Path scratch | Out-Null

    # 2. Full standard correctness suite. Expected: 1040 passed; about 13 minutes here.
    $step = 'full test suite'
    python -m pytest -q --tb=short --basetemp=scratch/pytest-run-all --junitxml=scratch/run_all-tests.xml
    if ($LASTEXITCODE -ne 0) { throw 'pytest failed' }

    # 3. Replay the final B alias; verify the supplied expected fills/book/proceeds.
    $step = 'worked-example replay'
    python -m run lob.replay 06_data/supplied/worked_example.jsonl --version B |
        Set-Content -LiteralPath scratch/worked_actual.jsonl -Encoding UTF8
    if ($LASTEXITCODE -ne 0) { throw 'replay failed' }
    python -m submission_tools check-worked scratch/worked_actual.jsonl
    if ($LASTEXITCODE -ne 0) { throw 'worked-example comparison failed' }

    # 4. Short 1k-only pipeline smoke; copied code, generated inputs and results in scratch/.
    $step = '1k benchmark smoke'
    python -m submission_tools smoke
    if ($LASTEXITCODE -ne 0) { throw 'benchmark smoke failed' }

    # Optional overnight reproduction. New sessions; never overwrite historic result folders.
    if ($Full) {
        Write-Output 'FULL benchmarks: expect about 7 h from saved worker times; allow 6-10 h on this laptop, longer elsewhere. This is an estimate.'
        if ((Read-Host 'Type RUN FULL to confirm the long measurements') -ne 'RUN FULL') { throw 'Full run not confirmed' }
        $step = 'generate/check full input catalog'
        python -m submission_tools data
        if ($LASTEXITCODE -ne 0) { throw 'data generation/checksums failed' }
        $session = 'reproduce_' + (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
        $manifest = '06_data/generated/reproduction/manifest.json'
        $parts = @('official','million','queue','liquidation','adversarial','churn')
        # Original candidates, full protocol, all registered original parts.
        foreach ($part in $parts) {
            $step = "full candidates / $part"
            python -m run bench.run_all --part $part --versions 'B1,B2,B3' --manifest $manifest --session ($session+'_candidates') --allow-long --skip-after-stop
            if ($LASTEXITCODE -ne 0) { throw 'candidate benchmark failed' }
        }
        # Final B3r on every part, then old variants on the post-attack additions.
        foreach ($part in ($parts + 'post_attack')) {
            $step = "full B3r / $part"
            python -m run bench.run_all --part $part --versions B3r --manifest $manifest --session ($session+'_final') --allow-long --skip-after-stop
            if ($LASTEXITCODE -ne 0) { throw 'B3r benchmark failed' }
        }
        $step = 'post-attack comparators'
        python -m run bench.run_all --part post_attack --versions 'B1,B2,B3' --manifest $manifest --session ($session+'_comparators') --allow-long --skip-after-stop
        if ($LASTEXITCODE -ne 0) { throw 'post-attack benchmark failed' }
        # A: declared single trial at 100k/1M; supplementary scope limited to 10k.
        foreach ($part in ($parts + 'post_attack')) {
            $step = "full A / $part"
            $maxSize = 10000
            if ($part -in @('official','million')) { $maxSize = 1000000 }
            python -m run bench.run_all --part $part --versions A --manifest $manifest --session ($session+'_baseline') --allow-long --skip-after-stop --baseline-protocol single-large --max-size $maxSize
            if ($LASTEXITCODE -ne 0) { throw 'baseline benchmark failed' }
        }
    }

    # 5. Saved-file dashboard (localhost:8501); -NoDashboard exits after the checks.
    $step = 'dashboard'
    if ($NoDashboard) { Write-Output 'OK: all requested checks complete; dashboard skipped (-NoDashboard)' }
    else {
        python -m streamlit run 04_dashboard/app.py
        if ($LASTEXITCODE -ne 0) { throw 'Streamlit failed' }
    }
} catch {
    Write-Error ("FAIL [$step]: " + $_.Exception.Message) -ErrorAction Continue
    exit 1
} finally {
    if ($null -ne $savedReproductionPath) { $env:PATH = $savedReproductionPath }
    Pop-Location
}

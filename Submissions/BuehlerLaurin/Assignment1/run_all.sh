#!/usr/bin/env bash
set -Eeuo pipefail
step='parse arguments'
trap 'printf "FAIL [%s], line %s\n" "$step" "$LINENO" >&2' ERR
full=false
no_dashboard=false
for arg in "$@"; do
    case "$arg" in
        --full) full=true ;;
        --no-dashboard) no_dashboard=true ;;
        *) printf 'Unknown option: %s\n' "$arg" >&2; exit 2 ;;
    esac
done
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

# 1. First use only: create .venv and install the pinned requirements.
step='create/install .venv'
if [[ ! -d .venv ]]; then
    python3 -m venv .venv
    .venv/bin/python -m pip install -r requirements.txt
else
    printf 'SKIP install: .venv exists\n'
fi
if [[ ! -x .venv/bin/python ]]; then printf 'FAIL: .venv has no Unix Python\n' >&2; exit 1; fi
export PATH="$PWD/.venv/bin:$PATH"
mkdir -p scratch

# 2. Full standard suite. Expected: 1040 passed; about 13 minutes on the author's laptop.
step='full test suite'
python -m pytest -q --tb=short --basetemp=scratch/pytest-run-all --junitxml=scratch/run_all-tests.xml

# 3. Final B replay and comparison with the supplied expected fills/book/proceeds.
step='worked-example replay'
python -m run lob.replay 06_data/supplied/worked_example.jsonl --version B > scratch/worked_actual.jsonl
python -m submission_tools check-worked scratch/worked_actual.jsonl

# 4. Short 1k-only pipeline smoke; every generated file stays inside scratch/.
step='1k benchmark smoke'
python -m submission_tools smoke

# Optional long reproduction: this branch is excluded from the default run.
if "$full"; then
    printf 'FULL benchmarks: about 7 h from saved worker times; allow 6-10 h on that laptop, longer elsewhere (estimate).\n'
    read -r -p 'Type RUN FULL to confirm the long measurements: ' confirmation
    if [[ "$confirmation" != 'RUN FULL' ]]; then printf 'FAIL: full run not confirmed\n' >&2; exit 1; fi
    step='generate/check full input catalog'
    python -m submission_tools data
    session="reproduce_$(date -u +%Y%m%dT%H%M%SZ)"
    manifest=06_data/generated/reproduction/manifest.json
    parts=(official million queue liquidation adversarial churn)
    # Original B candidates on the complete original grid.
    for part in "${parts[@]}"; do
        step="full candidates / $part"
        python -m run bench.run_all --part "$part" --versions B1,B2,B3 --manifest "$manifest" --session "${session}_candidates" --allow-long --skip-after-stop
    done
    # Final B on all parts, then historical comparators on post-attack cases.
    for part in "${parts[@]}" post_attack; do
        step="full B3r / $part"
        python -m run bench.run_all --part "$part" --versions B3r --manifest "$manifest" --session "${session}_final" --allow-long --skip-after-stop
    done
    step='post-attack comparators'
    python -m run bench.run_all --part post_attack --versions B1,B2,B3 --manifest "$manifest" --session "${session}_comparators" --allow-long --skip-after-stop
    # A uses its declared baseline protocol and supplementary scope.
    for part in "${parts[@]}" post_attack; do
        step="full A / $part"
        max_size=10000
        if [[ "$part" == official || "$part" == million ]]; then max_size=1000000; fi
        python -m run bench.run_all --part "$part" --versions A --manifest "$manifest" --session "${session}_baseline" --allow-long --skip-after-stop --baseline-protocol single-large --max-size "$max_size"
    done
fi

# 5. Open the saved-results dashboard; use --no-dashboard for terminal verification.
step='dashboard'
if "$no_dashboard"; then
    printf 'OK: all requested checks complete; dashboard skipped (--no-dashboard)\n'
else
    python -m streamlit run 04_dashboard/app.py
fi

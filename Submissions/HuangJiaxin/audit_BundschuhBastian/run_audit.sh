#!/usr/bin/env bash
# One command for the whole audit. Run from this folder:
#     bash run_audit.sh
# Needs git and Docker. Bastian's folder is only read; his scripts run in a temporary copy.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../.." && pwd)"
mkdir -p "$HERE/logs"

# 1. Code version: which commit changed the measured code last, and which commit the
#    results say they were produced with.
{
  echo "Reviewed folder history (latest first):"
  git -C "$REPO" log --format='%h %ad %s' --date=iso -- Submissions/BundschuhBastian | head -25
  echo
  for f in membership.py bench_time.py check_total.py bench_memory.py datagen.py; do
    echo "last change to $f: $(git -C "$REPO" log -1 --format='%h %s' -- "Submissions/BundschuhBastian/$f")"
  done
} > "$HERE/logs/code_version.txt"
cat "$HERE/logs/code_version.txt"

# 2. Everything else in a clean container with Bastian's Python version (3.11).
docker run --rm -v "$REPO":/repo -w /repo/Submissions/HuangJiaxin/audit_BundschuhBastian \
  -e PYTHONDONTWRITEBYTECODE=1 python:3.11-slim bash inner_audit.sh

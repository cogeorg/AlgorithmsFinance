# Phase 2 audit: WelscherYannick

This directory contains Ben Lavi's independent audit of Yannick Welscher's
Phase 1 submission.

- Upstream pull request: <https://github.com/cogeorg/AlgorithmsFinance/pull/23>
- Audited commit: `654516b585dd419ff63f37642d5c211891799fcb`
- Audited path: `Submissions/WelscherYannick/`
- Report: [`AUDIT_REPORT.md`](AUDIT_REPORT.md)
- Executable evidence: [`reproduce_audit.py`](reproduce_audit.py)

The reviewer did not edit the audited checkout. The reproduction script copies
the dashboard to a temporary directory before changing a result value for the
cache test.

## Reproduce

Create a detached worktree at the exact audited commit. This matters because
the reproduction script deliberately rejects a moving branch head or any
different repository commit.

```bash
cd /path/to/AlgorithmsFinance
AUDIT_TREE=/tmp/algorithmsfinance-yannick-654516b
AUDIT_ENV=/tmp/yannick-audit-venv
git worktree add --detach "$AUDIT_TREE" \
  654516b585dd419ff63f37642d5c211891799fcb
python3 -m venv "$AUDIT_ENV"
"$AUDIT_ENV/bin/python" -m pip install -r \
  "$AUDIT_TREE/Submissions/WelscherYannick/requirements.txt"

cd "$AUDIT_TREE/Submissions/WelscherYannick"
"$AUDIT_ENV/bin/python" -m pytest -p no:cacheprovider -ra

cd /path/to/AlgorithmsFinance
"$AUDIT_ENV/bin/python" \
  Submissions/LaviBen/phase2_welscher_yannick/reproduce_audit.py \
  "$AUDIT_TREE/Submissions/WelscherYannick"
```

After verification, remove the isolated checkout with
`git worktree remove "$AUDIT_TREE"`. The environment may be elsewhere; invoke
both commands with the same interpreter containing Yannick's pinned packages.

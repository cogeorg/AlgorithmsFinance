"""Check the unstaged submission in a clean copy, without staging or committing."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    env=dict(os.environ,GIT_OPTIONAL_LOCKS="0")
    return subprocess.run(["git",*args],cwd=ROOT,env=env,capture_output=True,check=True).stdout


def main():
    folder=ROOT/"evidence/submission_review"
    folder.mkdir(parents=True,exist_ok=True)
    before=dict(head=git("rev-parse","HEAD").decode().strip(),
                status=git("status","--porcelain").decode(),
                staged=git("diff","--cached","--name-only").decode())
    index=Path(git("rev-parse","--git-path","index").decode().strip())
    if not index.is_absolute():
        index=(ROOT/index).resolve()
    index_hash=sha(index) if index.exists() else None
    files=[Path(p) for p in git("ls-files","-z","--cached","--others","--exclude-standard","--",".").decode().split("\0") if p]
    if any(p.is_absolute() or ".." in p.parts or p.parts[0]=="work" for p in files):
        raise AssertionError("unexpected candidate path")
    if any(str(p).endswith(".jsonl.gz") for p in files):
        raise AssertionError("generated event streams must not enter the candidate submission")
    required=["README.md","REPORT.md","dashboard.html","lob/version_a.py","lob/version_b.py",
              "generate_orders.py","benchmark.py","benchmark_worker.py","BENCHMARK_METHODS.md",
              "REVISION.md","results/benchmark/raw_results.jsonl","results/benchmark/raw_results.csv",
              "results/benchmark/settings.json","results/benchmark/input_manifest.json"]
    assert all(Path(name) in files for name in required),"required submission file missing"
    measured=json.loads((ROOT/"results/benchmark/settings.json").read_text())
    for name,expected in measured["code_sha256"].items():
        assert sha(ROOT/name)==expected,f"measured file changed: {name}"
    steps=[]
    work=ROOT/"work"
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="submission-review-",dir=work) as temp:
        clean=Path(temp)/"Assignment1"
        clean.mkdir()
        for rel in files:
            target=clean/rel
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/rel,target)
        assert not (clean/"work").exists(),"generated work was accidentally copied"
        (clean/"work").mkdir()
        original_validation=sha(clean/"results/benchmark/validation.json")
        def run(name,*args):
            result=subprocess.run([sys.executable,"-B",*args],cwd=clean,capture_output=True,text=True,timeout=120)
            (folder/(name+".log")).write_text(result.stdout+result.stderr)
            if result.returncode:
                raise AssertionError(f"clean-copy step {name} failed: {(result.stdout+result.stderr)[-2000:]}")
            steps.append(dict(name=name,status="passed",command=["python3","-B",*args]))
            print(f"{name}: passed",flush=True)
            return result.stdout+result.stderr
        output=run("unit_tests","-m","unittest","discover","-s","tests","-v")
        assert re.search(r"Ran 63 tests",output) and "\nOK\n" in output
        expected=json.loads((clean/"data/worked_expected.json").read_text())
        for version in ("a","b"):
            output=run("worked_example_"+version,"-m","lob.replay","data/worked_example.jsonl","--version",version)
            result=json.loads(output)
            assert result["last_result"]==expected["market_sell_result"]
            assert result["remaining_orders"]==expected["remaining_orders"]
            assert result["total_gross_proceeds_tick_units"]==expected["gross_proceeds_tick_units"]
        run("saved_results_without_inputs","tools/validate_benchmarks.py","--skip-input-check",
            "--out","work/saved_results_audit.json")
        audit=json.loads((clean/"work/saved_results_audit.json").read_text())
        assert audit["status"]=="passed" and audit["all_generated_input_hashes_match"] is None
        assert sha(clean/"results/benchmark/validation.json")==original_validation
        run("dashboard_rebuild","tools/build_dashboard.py","--out","work/rebuilt_dashboard.html")
        assert sha(clean/"work/rebuilt_dashboard.html")==sha(clean/"dashboard.html"),"offline artifact is not reproducible"
        run("dashboard_saved_evidence","tools/validate_dashboard.py")
        run("benchmark_smoke","benchmark.py","--smoke","--out","work/smoke")
        run("smoke_results_validation","tools/validate_benchmarks.py","--results","work/smoke")
        smoke=json.loads((clean/"work/smoke/validation.json").read_text())
        assert smoke["primary_cases"]==10 and smoke["primary_repeat_rows"]==50
        assert smoke["primary_statuses"]=={"completed":50}
    assert git("rev-parse","HEAD").decode().strip()==before["head"],"HEAD changed"
    assert git("status","--porcelain").decode()==before["status"],"unexpected repository status change"
    assert git("diff","--cached","--name-only").decode()==before["staged"],"index contents changed"
    assert (sha(index) if index.exists() else None)==index_hash,"Git index was modified"
    result=dict(status="ready_for_user_review_commit_pending",candidate_files=len(files),
        candidate_bytes=sum((ROOT/p).stat().st_size for p in files),
        clean_copy_excluded_generated_inputs=True,clean_copy_steps=steps,
        all_63_tests_passed=True,worked_examples_exact=True,saved_results_checked_without_inputs=True,
        original_full_validation_preserved=True,rebuild_matches_browser_verified_html=True,
        smoke_cases=10,smoke_completed_repeats=50,measured_source_hashes_unchanged=True,
        git_head_unchanged=True,git_index_unchanged=True,staged_files=[],
        remote=git("remote","get-url","origin").decode().strip(),
        pending=["User review of REPORT.md and dashboard.html","Final authorized submission commit and commit identifier","Authorized submission to course repository"])
    (folder/"summary.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))


if __name__=="__main__":
    main()

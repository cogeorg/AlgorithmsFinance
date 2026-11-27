"""Verify a clean committed/tree export; does not rerun the benchmark matrix."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_checkpoints import ROOT, PREFIX, export


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref",default="HEAD")
    parser.add_argument("--save",action="store_true",help="save a verification record in results/evidence")
    args=parser.parse_args()
    repo=ROOT.parents[2]
    reference=subprocess.check_output(["git","rev-parse",args.ref],cwd=repo,text=True,stderr=subprocess.DEVNULL).strip()
    target=export(reference,ROOT/".preview/final-exports"/reference[:12])
    tracked=subprocess.check_output(["git","ls-tree","-r",reference,PREFIX],cwd=repo,text=True,stderr=subprocess.DEVNULL)
    files=0
    for line in tracked.splitlines():
        info,name=line.split("\t",1)
        expected=info.split()[2]
        data=(target/Path(name).relative_to(PREFIX)).read_bytes()
        actual=hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
        assert actual==expected,name
        files+=1
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1")
    env.pop("ORDERBOOK_VERSIONS",None)
    def run(arguments):
        result=subprocess.run([sys.executable,"-B",*arguments],cwd=target,env=env,
                              capture_output=True,text=True,timeout=40)
        assert result.returncode==0,result.stdout+result.stderr
        return result
    tests=run(["-m","unittest","discover","-s","tests","-v"])
    test_count=int(re.search(r"Ran (\d+) tests",tests.stderr).group(1))
    verified=json.loads(run(["verify_results.py"]).stdout)
    for version in ("baseline","revised"):
        worked=json.loads(run(["replay.py","data/worked_example.jsonl","--version",version]).stdout)
        expected=json.loads((target/"data/worked_expected.json").read_text())
        assert worked["last_result"]==expected["market_sell_result"]
        assert worked["remaining_orders"]==expected["remaining_orders"]
    deterministic=None
    if (target/"dashboard.py").exists():
        names=("dashboard.html","results/FINDINGS.md")
        before={name:(target/name).read_bytes() for name in names}
        run(["dashboard.py"])
        assert all((target/name).read_bytes()==value for name,value in before.items())
        deterministic=True
    for command in ("generate_orders.py","benchmark.py","replay.py"):
        run([command,"--help"])
    metadata=ROOT/"agent/PUBLICATION.json"
    base=json.loads(metadata.read_text())["course_base"] if metadata.exists() else "ae01998"
    names=subprocess.check_output(["git","diff","--name-only",base,reference],cwd=repo,text=True,stderr=subprocess.DEVNULL).splitlines()
    allowed={"Submissions/HardiKhushi/AGENTS.md","Submissions/HardiKhushi/PROGRESS.md","Submissions/HardiKhushi/AI_USAGE.md","Submissions/HardiKhushi/README.md"}
    assert all(name.startswith(PREFIX+"/") or name in allowed for name in names),"unrelated changed file"
    result=dict(reference=reference,exported_files_verified=files,tests=test_count,all_tests_passed=True,
                worked_examples_both_versions=True,saved_results=verified,
                deterministic_dashboard_rebuild=deterministic,cli_help_passed=True,
                prior_lab_audit_and_other_students_unchanged=True,
                scope="clean local Git export; benchmark matrix not rerun; not a remote clone")
    if args.save:
        folder=ROOT/"results/evidence"
        (folder/f"clean_export_{reference[:7]}.json").write_text(json.dumps(result,indent=2)+"\n")
        (folder/f"clean_export_{reference[:7]}.txt").write_text(tests.stdout+tests.stderr)
    print(json.dumps(result,indent=2))


if __name__=="__main__":
    main()

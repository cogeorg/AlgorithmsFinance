"""Second verification of the approved historical checkpoints, in clean exports."""
import argparse
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[1]
PREFIX="Submissions/HardiKhushi/Assignment1"
CHECKPOINTS=(("8270fac",None,0),("35125e8",None,40),("52a6c5e","baseline",22),
             ("3276644",None,43))


def export(commit,destination):
    metadata=ROOT/"agent/PUBLICATION.json"
    if metadata.exists():
        mapped=json.loads(metadata.read_text()).get("checkpoint_map",{}).get(commit)
        if mapped and mapped != "PENDING_APPROVAL":
            commit=mapped
    archive=subprocess.check_output(["git","archive",commit,PREFIX],cwd=ROOT.parents[2],stderr=subprocess.DEVNULL)
    destination.mkdir(parents=True,exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        for member in source.getmembers():
            target=destination/member.name
            assert target.resolve().is_relative_to(destination.resolve())
            if member.isdir():
                target.mkdir(parents=True,exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(source.extractfile(member).read())
            else:
                raise ValueError(f"unexpected archive entry {member.name}")
    return destination/PREFIX


def main(save=True):
    scratch=ROOT/".preview/checkpoints"
    output=ROOT/"results/evidence/checkpoints"
    output.mkdir(parents=True,exist_ok=True)
    results=[]
    for commit,version,expected_count in CHECKPOINTS:
        target=export(commit,scratch/commit)
        if not expected_count:
            assert not list((target/"orderbook").glob("*.py"))
            assert (target/"assignment/AlgorithmsFinance_Exercise1.pdf").exists()
            results.append(dict(commit=commit,check="source organization; no engine yet",passed=True))
            continue
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1")
        env.pop("ORDERBOOK_VERSIONS",None)
        if version: env["ORDERBOOK_VERSIONS"]=version
        run=subprocess.run([sys.executable,"-B","-m","unittest","discover","-s","tests","-v"],
                           cwd=target,env=env,capture_output=True,text=True,timeout=30)
        text=run.stdout+run.stderr
        if save:
            (output/f"{commit}.txt").write_text(text)
        count=int(re.search(r"Ran (\d+) tests",text).group(1))
        assert count==expected_count
        if commit=="35125e8":
            assert run.returncode!=0 and "FAILED (errors=37)" in text
            assert not list((target/"orderbook").glob("*.py"))
        else: assert run.returncode==0,text
        results.append(dict(commit=commit,tests=count,returncode=run.returncode,passed=True,
                            interpretation="expected missing modules" if commit=="35125e8" else "passing suite"))
    if save:
        (ROOT/"results/evidence/checkpoint_verification.json").write_text(json.dumps(results,indent=2)+"\n")
    print(json.dumps(results,indent=2))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-save",action="store_true")
    main(save=not parser.parse_args().no_save)

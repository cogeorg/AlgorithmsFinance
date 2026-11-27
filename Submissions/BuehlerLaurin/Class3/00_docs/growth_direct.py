"""Growth isolation on Windows: timeout the real interpreter, not a venv launcher.

The venv redirector can create a second process. Preserve the initial growth
grid, then rerun every cell with the base interpreter and explicit venv site
packages so a timeout kills the actual single computation process.
"""
import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    root=Path.cwd(); d=root/(root/'03_results/LATEST.txt').read_text(encoding='utf-8').strip()
    sys.path.insert(0,str(root/'01_code'))
    from bench.harness import run_with_timeout
    assert (d/'growth.csv').exists(),'Run after the main grid finishes'
    shutil.copyfile(d/'growth.csv',d/'growth_launcher.csv')
    if os.name=='nt':
        command="$workers = Get-CimInstance Win32_Process -Filter \"Name = 'python.exe'\" | Where-Object { $_.CommandLine -like '*-B run.py bench.growth_cell --version*' }; $workers | Format-List ProcessId,ParentProcessId,CommandLine; $workers | ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }"
        cleanup=subprocess.run(['powershell','-NoProfile','-Command',command],capture_output=True,text=True,check=True)
        (d/'growth_timeout_cleanup.txt').write_text(cleanup.stdout+cleanup.stderr,encoding='utf-8')
        print('Timed-out launcher descendant cleanup: '+(cleanup.stdout.strip() or 'no workers remaining'),flush=True)
    rows=[]
    site_packages=str(Path(sys.prefix)/('Lib/site-packages' if os.name=='nt' else f'lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages'))
    for version in ['A','B']:
        for n in [1000,2000,4000,8000]:
            output=d/f'growth_direct_{version}_{n}.json'
            argv=['run.py','bench.growth_cell','--version',version,'--n',str(n),'--out',str(output)]
            bootstrap=f'import site,sys,runpy; site.addsitedir({site_packages!r}); sys.argv={argv!r}; runpy.run_path(\'run.py\',run_name=\'__main__\')'
            cmd=[sys._base_executable,'-B','-c',bootstrap]
            result=run_with_timeout(cmd,60)
            (d/f'growth_direct_{version}_{n}.log').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
            row=dict(version=version,N=n,status=result['status'],seconds='',repeats_requested=5,limit_s=60)
            if result['status']=='ok':
                row['seconds']=json.loads(output.read_text(encoding='utf-8'))['run_median_s']
            rows.append(row)
            print(f'Direct-process growth {version} N={n}: {row["status"]} {row["seconds"]}',flush=True)
    with (d/'growth.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    (d/'GROWTH_PROTOCOL.txt').write_text('Final growth.csv uses direct base-interpreter cells, explicit existing venv site-packages, one warm-up and five repeats, 60 s whole-process limit. Original launcher grid retained in growth_launcher.csv and original logs, excluded from final tables.\n',encoding='utf-8')
    assert all(r['status'] in ('ok','stopped') for r in rows)
    print('DIRECT-PROCESS GROWTH GRID: COMPLETE')


if __name__=='__main__':
    main()

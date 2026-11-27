"""Select one controlled case and delegate unchanged measurements to benchmark.py."""
import argparse
from pathlib import Path
import benchmark as bm

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--count",type=int,required=True)
    p.add_argument("--seed",type=int,required=True)
    p.add_argument("--experiment",choices=("market-sell","queue-concentration","cancel-churn"),required=True)
    p.add_argument("--levels",type=int,default=1000)
    p.add_argument("--sale-percent",type=int)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args(argv)
    if a.count<1 or not 1<=a.levels<6000000:p.error("Invalid count or levels")
    args=argparse.Namespace(counts=[a.count],seeds=[a.seed],experiments=[a.experiment],
        scenarios=list(bm.SCENARIOS),levels=a.levels,versions=["baseline","revised"],
        out=a.out,data_dir=bm.ROOT/"data",worker_seconds=60,campaign_seconds=900,
        payload_mib=128,traced_mib=512,label="final-controlled")
    cases=bm.case_matrix(args)
    if a.experiment=="market-sell":cases=[c for c in cases if c["sale_percent"]==a.sale_percent]
    if a.experiment=="queue-concentration":cases=[c for c in cases if c["levels"]==a.levels]
    if len(cases)!=1:p.error("Select exactly one case")
    return bm.campaign(args,cases)

if __name__=="__main__":raise SystemExit(main())


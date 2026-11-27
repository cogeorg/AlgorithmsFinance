"""Full BTC 1y A/B value and boundary comparison, not a speed benchmark."""
import json
import sys
from pathlib import Path
from amput.a import price_with_boundary as A
from amput.b import price_with_boundary as B
from amput.data import load_calibrate


def main():
    root=Path(__file__).resolve().parents[2]
    sys.path.insert(0,str(root/'02_tests'))
    from test_differential import compare
    w=load_calibrate(root.parents[2]/'Class3/data/hourly/BTCUSDT.csv','1y')
    a=A(*w.params); b=B(*w.params)
    exceptions=compare(a,b,w.params[1])
    record=dict(N=w.params[-1],K=w.params[1],A=a.value,B=b.value,
                absolute_difference=abs(a.value-b.value),near_tie_boundary_exceptions=exceptions,
                near_tie_layers_A=sum(a.near_ties),near_tie_layers_B=sum(b.near_ties))
    (root/'00_docs/BTC1Y_DIFFERENTIAL.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(record,indent=2))
    print('BTC 1y A/B DIFFERENTIAL: PASS')


if __name__=='__main__':
    main()

"""BTC one-year baseline profiling workload, separate from timing runs."""
from pathlib import Path
from amput.data import load_calibrate
from amput.a import price_with_boundary


def main():
    root=Path(__file__).resolve().parents[2]
    window=load_calibrate(root.parents[2]/'Class3/data/hourly/BTCUSDT.csv','1y')
    result=price_with_boundary(*window.params)
    print(f'Profile A BTC 1y: N={window.params[-1]}, value={result.value:.12g}')


if __name__=='__main__':
    main()

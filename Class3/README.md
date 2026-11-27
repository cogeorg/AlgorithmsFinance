# Classes 3 and 4

`class3_evidence.py` produces the profiling figures on the Class 3 and Class 4 slides for
`FillMarketSell`, `PriceAmericanPut`, `RandomizedQuickSort` and
`EstimateMeanLoss`. It implements the four procedures, checks them against
independent references, times them, records peak traced allocations, and
profiles one `PriceAmericanPut` call.

From the repository root (Python 3.9 or later):

```bash
git pull                                            # get the latest version
python3 Class3/class3_evidence.py --validate-only # correctness checks; standard library only
python3 -m pip install matplotlib                   # once, for the figures
python3 Class3/class3_evidence.py                 # full run, about 20 seconds
```

Results are written to `Class3/output/` (ignored by git):

| File | Content |
|---|---|
| `FillMarketSell.pdf`, `PriceAmericanPut.pdf`, `RandomizedQuickSort.pdf`, `EstimateMeanLoss.pdf` | Runtime and memory (or accuracy) figures |
| `Measurements.csv`, `QuickSortSeeds.csv`, `MeanLossSeeds.csv` | Raw measurements |
| `Metadata.json` | Machine, Python version, validation results, measurement protocol |
| `Profile_PriceAmericanPut.txt` | `cProfile` report of one call |
| `SlideMetrics.tex` | Last-step time ratios quoted on the slides |

Absolute times depend on your machine. Compare growth ratios with the slides,
not milliseconds. Use `--out DIR` to write elsewhere and `--replot` to redraw
the figures from CSV files already in the output folder.

The lab data and their documentation are in `data/`; see `data/README.md`.

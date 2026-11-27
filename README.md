# Algorithms in Finance

Python code for the Frankfurt School Master in Financial Technology module
*Algorithms in Finance*.

This repository is linked from the course folder as `50_code/`.

| Path | Purpose |
|---|---|
| `Class1-2/` | Code for the Classes 1–2 slides, including the runtime and profiling figures |
| `Class3/` | Code for the Class 3–4 slides; see `Class3/README.md` to reproduce the profiling figures |
| `Class3/data/` | Hourly prices for the Class 3 lab (Bitcoin, gold, 38 more assets; S&P 500 via a fetch script); see `Class3/data/README.md` |
| `Submissions/` | Place your own lab and exercise files here |

Instructor literature crawlers and glossary generators stay in the course
teaching tree (`tools/`), not in this repository.

## Class 1–2 figures

The scaling plots on the Classes 1–2 slides are produced by
`Class1-2/class1_profiling_demo.py`. From the course root:

```bash
python3 50_code/Class1-2/class1_profiling_demo.py
```

The script implements `contains`, `max_loss`, and `duplicate_pairs`, checks the
worked examples, times unprofiled batches, then runs a separate `cProfile`
pass. It writes PDFs, CSV measurements, metadata, profile reports, and
`SlideMetrics.tex` to `10_overleaf/figures/Class1_Performance/`. Rebuild the
slides after rerunning measurements. Matplotlib is required only for figure
export.

# Reproducibility Check

Isolated copy of local repository files; excludes .git, work, caches, and virtual environments. This is not a fresh remote clone.

Python: 3.13.0 (v3.13.0:60403a5409f, Oct  7 2024, 00:37:40) [Clang 15.0.0 (clang-1500.3.9.4)]

| Command | Exit code |
| --- | --- |
| `python3 -B run_tests.py` | 0 |
| `python3 -B validate_data.py` | 0 |
| `python3 -B generate_data.py --seed 42 --include-empty-queries` | 0 |
| `python3 -B validate_data.py` | 0 |
| `python3 -B benchmark.py` | 0 |
| `python3 -B dashboard.py` | 0 |
| `python3 -B build_report.py` | 0 |

- All seven documented commands exited successfully.
- Fixed-seed input bytes match the original saved dataset.
- Regenerated timings are separate observations, not expected to match the original times.
- English dashboard and report regenerate from the new measurements.
- No third-party Python packages were needed by these commands.
- Browser interaction checks are recorded separately in dashboard_validation.txt.

The original `results/` files were not overwritten. Full command output is saved in `reproducibility.json`; temporary copies/logs under `work/` are excluded from Git.

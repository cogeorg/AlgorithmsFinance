import sys
from pathlib import Path

# Make the Class3 modules importable as top-level modules (american_put, calibrate, ...).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

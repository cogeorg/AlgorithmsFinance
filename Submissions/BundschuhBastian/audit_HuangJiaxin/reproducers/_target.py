"""Locate the audited code (Submissions/HuangJiaxin) and import it without editing it."""
import sys
from pathlib import Path

TARGET = Path(__file__).resolve().parents[3] / "HuangJiaxin"
AUDITED_COMMIT = "47ec3ae1c62af0c8ef142df5f11002d44fb3dc10"
if str(TARGET) not in sys.path:
    sys.path.insert(0, str(TARGET))

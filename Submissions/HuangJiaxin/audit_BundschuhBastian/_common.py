"""Shared helpers for the audit scripts. Nothing here writes into Bastian's folder."""
import sys
from pathlib import Path

sys.dont_write_bytecode = True          # never create __pycache__ in the reviewed folder

HERE = Path(__file__).resolve().parent
TARGET = (HERE / ".." / ".." / "BundschuhBastian").resolve()
LOGS = HERE / "logs"
LOGS.mkdir(exist_ok=True)


def import_target():
    """Make Bastian's modules importable without copying or editing them."""
    if str(TARGET) not in sys.path:
        sys.path.insert(0, str(TARGET))
    import membership
    import datagen
    return membership, datagen


class Report:
    """Collects PASS / FAIL lines and writes them to logs/<name>.txt."""

    def __init__(self, name):
        self.name, self.lines, self.failed = name, [], 0

    def check(self, ok, text):
        self.lines.append(("PASS " if ok else "FAIL ") + text)
        self.failed += 0 if ok else 1
        print(self.lines[-1])

    def note(self, text):
        self.lines.append("     " + text)
        print(self.lines[-1])

    def save(self):
        summary = f"{self.name}: {len(self.lines)} lines, {self.failed} FAIL"
        (LOGS / f"{self.name}.txt").write_text("\n".join(self.lines + ["", summary]) + "\n")
        print(summary)

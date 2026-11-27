# Pre-implementation failing baseline

Date: 21 November 2026 (Europe/Berlin)
Interpreter: CPython 3.14.7
Checkpoint commit: `8788d13b6a59aadfa9785cbc31967dce2cc4e4fe`

The public contract, independent expected results, copied-fixture integrity
checks and shared two-version test suite existed before either implementation.
There was no `orderbook/` directory when this command ran.

## Command

```bash
cd Submissions/LaviBen/Assignment1
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

## Observed result

- Exit status: `1`
- Tests run: `20`
- Fixture/generator tests passing: `4`
- Behavioral tests failing: `16`
- Errors: `0`
- Failure reason for every behavioral test:

  ```text
  required implementations are missing or failed to import:
  {
    'baseline': "ModuleNotFoundError: No module named 'orderbook'",
    'revised': "ModuleNotFoundError: No module named 'orderbook'"
  }
  ```

The passing tests independently confirmed before implementation that:

- every copied asset matches its recorded byte count and SHA-256;
- all five supplied streams have exactly 10,000 ordered, unique event IDs and
  the frozen event-type counts;
- the supplied generator is locally seeded and reproducible; and
- the worked expected file contains maker order `b1`, `b2`, `b3`, `b4`, fill
  quantities `1`, `1`, `3`, `1` BTC and integer gross proceeds corresponding
  to `359400.00` USD.

This is evidence that the suite detects missing behavior. It is not evidence
that the future implementation is correct; that requires the unchanged suite,
invariants, differential checks and reasoning after implementation.

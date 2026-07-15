# Porting note 001: accumulation conversation windows

This pass covers the first accumulation parity gap from `reference/rENA/R/ena.accumulate.data.R`
and `reference/rENA/R/accumulate.data.R`.

- `ena.accumulate.data` accepts separate `units`, `conversation`, `codes`, and optional
  `metadata` data frames, then combines them before processing.
- In `window = "Conversation"`, rENA groups by the requested conversation columns plus
  unit columns and creates one co-occurrence vector per unit-conversation group. It does
  not repeat that vector for every source line.
- Endpoint metadata follows rENA's `add.metadata` behavior by retaining only metadata
  columns with one unique value per unit.
- `SeperateTrajectory` is accepted as a migration alias for rENA helper code that used
  the misspelled trajectory label.

The tests in `tests/test_accumulation_smoke.py` now lock these behaviors with small
hand-computed fixtures based on the R source.

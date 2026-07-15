# Changelog

All notable changes to ena-python (formerly pyENA) are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is [SemVer](https://semver.org/).

## [Unreleased]

### Changed — project, distribution, and import names (breaking)

The project, the GitHub repository, and the PyPI distribution are now **ena-python**;
the module is **`ena_python`**. It was pyENA. The CLI command is still `pyena`.

```python
pip install ena-python
import ena_python
```

The rename was forced by an unrelated package that already owns `pyena` on PyPI — and
that installs a top-level module named `pyena` as well. Shipping our own `pyena` module would have
collided with it silently: two Python ENA ports are exactly the pair someone would
install together to compare, and whichever landed second would win. The distribution
name follows the module name for consistency.

`import ena_python` rather than `import ena`, despite `ena` being unclaimed, because
the package exports a top-level function named `ena` — `from ena import ena` reads
badly. Done now while there is no installed base; it only gets more expensive later.

### Parity

Closes the parity gaps 0.1.0 shipped with: trajectory models, the Conversation
window, and the four advanced rotations are now pinned to real compiled rENA 0.3.1
instead of being smoke-tested only.

### Fixed

- **Trajectory points lost the conversation column.** rENA binds the trajectory frame
  to points for Trajectory models and the metadata frame otherwise
  (`ena.make.set.R:257-262`); pyENA always bound metadata. Trajectory points are one
  row per unit-and-step, so without `conv` the steps could not be told apart or
  ordered — the entire point of a trajectory. `points` now carries `unit`,
  `ENA_UNIT`, and `conv` for Trajectory models, plus any metadata columns (a superset
  of rENA, which drops them, so grouping and coloring still work).

### Added

- Numeric parity for the **Conversation window** and **both trajectory models**, at
  accumulation *and* full-model level (points, variance, eigenvalues, center vector,
  node positions). All matched rENA on arrival; the gap was evidence, not defects.
- Numeric parity for the **generalized, regression, regression_2, and hENA rotations**
  across 9 cases — numeric and categorical targets (`gmr` branches on this), combined
  x+y, and control variables. All 9 match rENA across every dimension.
- A rotation fixture dataset (8 units × 4 codes) with unit-level categorical and
  numeric covariates, and model-level fixtures per model type.

### Changed

- **`rotate_by_regression` deliberately diverges from rENA on the y axis** when given
  both `x_var` and `y_var`. rENA intends to regress y on the x-deflated points
  (`V <- defA`), but its `with.ena.matrix` helper rebinds `V` to the raw points unless
  passed a `V =` argument, and a refactor dropped it — the commented-out line above
  the call still shows it. rENA therefore returns axes that are strongly collinear
  (cosine ~0.8–0.97), making its "2D" projection nearly one-dimensional, while its
  sibling `ena.rotate.by.generalized` deflates correctly on the same data. pyENA
  deflates, giving orthogonal axes; the x axis still matches rENA exactly. A test
  fails if rENA ever fixes this, prompting pyENA to match it.
- Regression axes are named after the predictor (`score_reg`) rather than rENA's
  `A & B_reg`, which comes from the same string/formula confusion (`all.vars()` on a
  string returns nothing, so rENA falls back to the first edge name). Cosmetic; the
  vectors match.

## [0.1.0] — 2026-07-15

First public release. Addresses the findings of the 2026-07-15 technical review of
0.0.1 (internal alpha). **Numeric output changes**: `variance` and `eigenvalues` were
wrong on data of rank > `dimensions`, so results from 0.0.1 should be regenerated.

### Fixed

- **`variance` was normalized over only the retained dimensions** instead of the total
  across all of them, overstating every retained dimension whenever
  `rank(points) > dimensions`. rENA normalizes by the full projection
  (`ena.make.set.R:332-335`). On a 6-unit / 4-code dataset, pyENA reported dimension 1
  as `0.810305` where rENA reports `0.738364` — 7.2 percentage points off. The 3-unit
  toy fixture has rank 2, so its ~0 third singular value made the two denominators
  agree and hid this. Now guarded by a rank-3 fixture.
- **`eigenvalues` were raw `s²`, truncated to `dimensions`**, rather than rENA's
  `prcomp` `sdev² = s²/(n−1)` across all dimensions (`ena.svd.R:57`). The values were
  off by exactly a factor of `n−1` (verified: 2.0 at n=3, 5.0 at n=6). Nothing asserted
  them, so the divergence was invisible.
- **Infinite forward moving-stanza windows** subtracted a head that rENA does not.
  rENA clamps an infinite forward window to the row count (`ena.cpp:236`), driving
  `headRows <= 0` and skipping head subtraction (`ena.cpp:274-276`); pyENA substituted
  `0`. Finite windows and the common `forward=0` case were unaffected. The window is
  now pinned to rENA's compiled kernel across four configurations.
- **FastAPI endpoints returned 422 for every request** when the module carried
  `from __future__ import annotations`: `ENARequest` is defined inside `create_app()`,
  so PEP 563 string annotations resolved against module globals, and FastAPI silently
  demoted the body model to a query parameter.
- `mypy src/pyena` now passes. It previously failed both on `plotting.py` type errors
  and because a pinned `python_version = "3.10"` made mypy parse numpy ≥2.2 stubs
  (PEP 695 syntax) under 3.10 rules.

### Changed

- **`to_dict()` no longer echoes the input dataset by default.** `raw` and
  `row_connection_counts` are now opt-in via `to_dict(include_raw=True)` (CLI:
  `--include-raw`). ENA is routinely run over transcripts containing personal data,
  and echoing the whole input into every result — CLI output, API responses — widened
  the exposure of anything stored or sent, for payload bloat and no analytic gain.
- `variance` and `eigenvalues` now cover **all** dimensions, as in rENA, not just the
  retained `dimensions`. `points`, `nodes`, and `rotation` remain sliced to
  `dimensions`.
- Metadata columns that vary within a unit still get dropped, but now emit a
  `UserWarning` naming them instead of disappearing silently.
- The golden-fixture generator prefers the **installed, compiled rENA** package and
  records provenance (oracle mode, rENA/R versions, platform) in every fixture. It
  refuses to write a fixture from the pure-R fallback unless
  `PYENA_ALLOW_NONAUTHORITATIVE_ORACLE=1`, because those fallbacks re-implement
  `ena.cpp` the way pyENA does — a fixture built from them could only show pyENA
  agreeing with a re-implementation of itself. The fallback was previously gated on
  `gfortran`, which `ena.cpp` (C++) does not need, so most machines silently used it.

### Added

- Rank-3 golden fixture (6 units × 4 codes → 6 dimensions, ~13% of variance beyond
  dimension 2) that discriminates the variance/eigenvalue fixes.
- Parity assertions for `eigenvalues` and full-width `variance`; a provenance check
  that fails if a non-authoritative fixture is ever committed.
- Request size cap on the web app (`create_app(max_rows=...)` /
  `PYENA_WEB_MAX_ROWS`, default 100000), returning HTTP 413.
- HTML escaping for dataset-derived Plotly labels. Plotly interprets a limited HTML
  subset in `text`/`hovertext`, so markup in a unit or code name was live in exported
  HTML.
- `[parquet]` extra. `io.read_table` advertised `.parquet` but no engine was declared;
  it now raises an actionable error naming the extra.
- CI: `ruff format --check`, `mypy`, Python 3.13, and a build job running
  `twine check --strict` plus a clean-environment wheel import.

### Removed

- `scikit-learn` from the runtime dependencies. It was never imported, and it is heavy
  or unavailable under Pyodide — a real cost against the browser goal.
- Unused optional dependencies: `networkx` (`[plot]`), `numba`/`polars` (`[accel]`,
  extra dropped), `hypothesis` (`[dev]`).

### Notes

- The web app is built lazily, so importing `pyena.web.api` no longer constructs a
  FastAPI instance — or raises when the `[web]` extra is absent.
- Not published to PyPI: the `pyena` name belongs to an unrelated project.

[0.1.0]: https://github.com/HUDongpin/ena-python/releases/tag/v0.1.0

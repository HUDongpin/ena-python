# Changelog

All notable changes to ena-python (formerly pyENA) are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is [SemVer](https://semver.org/).

## [0.2.1] — 2026-07-16

Documentation and metadata only — no code changes. PyPI renders a project's page from
the README **inside the uploaded artifact**, so the stale lines below were visible on
the 0.2.0 PyPI page and could only be corrected by publishing a fixed build.

### Fixed (docs/metadata)

- The README status line still read "early release (0.1.0)" — on the 0.2.0 PyPI page.
  Now version-agnostic, and it no longer claims parts are unverified: since the
  mean-rotation completion basis was pinned, every numeric path is checked against
  compiled rENA 0.3.1.
- The parity table still marked the mean rotation "Partly — MR1/SVD2 only"; it has been
  verified across its full completion basis since before 0.2.0.
- The wheel was described as "~147 KB". That was its *uncompressed* contents; twine's
  upload log suggested 74 KB, but that is the upload payload including the metadata
  form. The wheel pip actually downloads is **~53 KB**, verified against the published
  0.2.0 artifact.
- Browser-demo timings replaced with a measured cold run against the published 0.2.0
  (16.1 s total; "no further dependencies" confirmed) instead of pre-release estimates.
- Trove classifiers: Development Status Pre-Alpha → **Alpha**; added Python **3.13**
  (tested in CI) and **3.14** (this project's native development ran on CPython 3.14.6
  throughout, and the Pyodide demo runs on 3.14.2).

## [0.2.0] — 2026-07-16

Everything verified since 0.1.0. **Upgrade if you installed 0.1.0 from PyPI**: it
carries two of the bugs fixed here (duplicate-index row misalignment; the pandas 3 NaN
crash) and its accumulation is 10x slower. Builds from the `v0.1.0` git tag additionally
predate the trajectory fix and the parity work below.

### Removed

- **SciPy is no longer a dependency.** ena-python needs only NumPy and pandas. Exactly
  three SciPy calls existed (`norm.ppf`, `pearsonr`, `spearmanr`), all in
  `ena_python.stats`; `statistics.NormalDist().inv_cdf` and `numpy.corrcoef` (over
  `Series.rank()` for Spearman) give the same answers to ~1e-15 — machine epsilon, six
  orders of magnitude inside the 1e-9 tolerance the rENA parity fixtures assert. Those
  fixtures still pass unchanged. Correlations keep working, so nothing moved behind an
  extra and no caller breaks.

  It removes 13.2 MB of a 20.4 MB scientific stack under Pyodide — 65% of a browser
  page's download, for functions it may never call — and takes a clean install from
  219 MB to 120 MB.

### Performance

Accumulation is **10x faster** on rENA's `RS.data` (3824 rows / 48 units): 0.0714s →
0.0071s; end to end 0.0731s → 0.0086s. Output is unchanged — every rENA parity fixture
still passes, and a differential test compares the new kernel against the previous
implementation across 2304 configurations.

- `vector_to_ut` / `rows_to_co_occurrences` use cached upper-triangle index arrays
  instead of rebuilding a list of tuples per call (`vector_to_ut` alone: 15x).
- `ref_window_matrix` uses prefix sums rather than a per-row Python loop. Every quantity
  rENA needs — window, head, tail — is a contiguous row-range sum, so each becomes one
  subtraction (kernel: 24-63x).
- `_merge_columns` uses `Series.str.cat` instead of `.agg(sep.join, axis=1)`, a row-wise
  apply. **This was the real bottleneck at 73% of accumulation** — profiling contradicted
  the design doc, which had pointed at the window kernel (only 23%).
- The per-conversation loop no longer builds a DataFrame per group; codes are sliced once
  into an ndarray and results written at their original row positions.

Exactness: for 0/1 code columns — what ENA takes — prefix-sum differences are bit-for-bit
identical to fresh sums. Non-binary inputs can differ by ~1e-13 (cumulative vs direct
summation rounding), far below any tolerance here.

### Fixed

- **Co-occurrences could land on the wrong row when the input index had duplicate
  labels.** The old code built one frame per conversation and stitched them with
  `pd.concat(pieces).sort_index()`; that orders rows group-by-group, and tied labels
  leave the sort unable to restore row order. A row with no co-occurrence could be
  credited with a neighbour's. Found while vectorizing, pinned by
  `test_accumulation_rows_stay_aligned_with_a_duplicate_index`.
- **`_merge_columns` raised `TypeError` on pandas 3 when a key column held NaN.** Pandas 3
  changed `.astype(str)` to leave NaN as NaN rather than stringifying it, so the row-wise
  `sep.join` hit a float. Missing keys again become the literal "nan", as under pandas 2.

### Parity

Closes the parity gaps 0.1.0 shipped with: trajectory models, the Conversation
window, and the four advanced rotations are now pinned to real compiled rENA 0.3.1
instead of being smoke-tested only.

- **Trajectory points lost the conversation column.** rENA binds the trajectory frame
  to points for Trajectory models and the metadata frame otherwise
  (`ena.make.set.R:257-262`); ena-python always bound metadata. Trajectory points are one
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
- Numeric parity for **`cohens_d`, `ena_correlations`, and `ena_correlation`** — the
  last functions with no numeric backing. All match rENA. The review had flagged that
  rENA's `fun_cohens.d` "may return a signed value", which would have flipped the
  direction of every group comparison: it does not. rENA takes
  `abs(mean(x) - mean(y))` (`R/cohens.d.R`), so both are absolute and agree. Mirrored
  x/y fixtures pin that convention so a future signed rewrite fails loudly.

### Changed

- **`rotate_by_regression` deliberately diverges from rENA on the y axis** when given
  both `x_var` and `y_var`. rENA intends to regress y on the x-deflated points
  (`V <- defA`), but its `with.ena.matrix` helper rebinds `V` to the raw points unless
  passed a `V =` argument, and a refactor dropped it — the commented-out line above
  the call still shows it. rENA therefore returns axes that are strongly collinear
  (cosine ~0.8–0.97), making its "2D" projection nearly one-dimensional, while its
  sibling `ena.rotate.by.generalized` deflates correctly on the same data. ena-python
  deflates, giving orthogonal axes; the x axis still matches rENA exactly. A test
  fails if rENA ever fixes this, prompting ena-python to match it.
- `ena_correlations` now raises a `ValidationError` naming the missing dimension and
  the `dimensions=` value needed, instead of a bare pandas `KeyError`, when asked for a
  dimension the model did not project. (ena-python slices `points` to `dimensions`;
  rENA keeps every dimension and never hits this.)
- Regression axes are named after the predictor (`score_reg`) rather than rENA's
  `A & B_reg`, which comes from the same string/formula confusion (`all.vars()` on a
  string returns nothing, so rENA falls back to the first edge name). Cosmetic; the
  vectors match.

## [0.1.0] — 2026-07-15

First public release.

> **Note on this version number.** The wheel uploaded to PyPI as `ena-python` 0.1.0
> includes the rename below. The git tag `v0.1.0` predates it and still builds the
> `pyena` module, because the tag was cut before the rename. Nothing depends on the tag;
> the PyPI artifact is authoritative for what 0.1.0 means. Verified against the wheel
> itself: the PyPI 0.1.0 build also already contains the trajectory `conv` fix and the
> trajectory/Conversation/rotation parity work recorded under [0.2.0], which landed
> between the tag and the upload.

### Changed — project, distribution, and import names (breaking)

The project, the GitHub repository, and the PyPI distribution are now **ena-python**;
the module is **`ena_python`**, and the CLI command is **`ena-python`**. It was pyENA.

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

### Fixed

Addresses the findings of the 2026-07-15 technical review of 0.0.1 (internal alpha).
**Numeric output changes**: `variance` and `eigenvalues` were wrong on data of rank >
`dimensions`, so results from 0.0.1 should be regenerated.

- **`variance` was normalized over only the retained dimensions** instead of the total
  across all of them, overstating every retained dimension whenever
  `rank(points) > dimensions`. rENA normalizes by the full projection
  (`ena.make.set.R:332-335`). On a 6-unit / 4-code dataset, ena-python reported dimension 1
  as `0.810305` where rENA reports `0.738364` — 7.2 percentage points off. The 3-unit
  toy fixture has rank 2, so its ~0 third singular value made the two denominators
  agree and hid this. Now guarded by a rank-3 fixture.
- **`eigenvalues` were raw `s²`, truncated to `dimensions`**, rather than rENA's
  `prcomp` `sdev² = s²/(n−1)` across all dimensions (`ena.svd.R:57`). The values were
  off by exactly a factor of `n−1` (verified: 2.0 at n=3, 5.0 at n=6). Nothing asserted
  them, so the divergence was invisible.
- **Infinite forward moving-stanza windows** subtracted a head that rENA does not.
  rENA clamps an infinite forward window to the row count (`ena.cpp:236`), driving
  `headRows <= 0` and skipping head subtraction (`ena.cpp:274-276`); ena-python substituted
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
  `ENA_PYTHON_ALLOW_NONAUTHORITATIVE_ORACLE=1`, because those fallbacks re-implement
  `ena.cpp` the way ena-python does — a fixture built from them could only show ena-python
  agreeing with a re-implementation of itself. The fallback was previously gated on
  `gfortran`, which `ena.cpp` (C++) does not need, so most machines silently used it.

### Added

- Rank-3 golden fixture (6 units × 4 codes → 6 dimensions, ~13% of variance beyond
  dimension 2) that discriminates the variance/eigenvalue fixes.
- Parity assertions for `eigenvalues` and full-width `variance`; a provenance check
  that fails if a non-authoritative fixture is ever committed.
- Request size cap on the web app (`create_app(max_rows=...)` /
  `ENA_PYTHON_WEB_MAX_ROWS`, default 100000), returning HTTP 413.
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
- Released to PyPI as `ena-python` (see Unreleased): the `pyena` name belongs to
  an unrelated project, so this release went out under the new name.

[0.2.1]: https://github.com/HUDongpin/ena-python/releases/tag/v0.2.1
[0.2.0]: https://github.com/HUDongpin/ena-python/releases/tag/v0.2.0
[0.1.0]: https://github.com/HUDongpin/ena-python/releases/tag/v0.1.0

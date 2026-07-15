# `reference/` — rENA reference material

ena-python is a port of [rENA](https://gitlab.com/epistemic-analytics/qe-packages/rENA).
This directory holds the reference material used to establish parity.

## What is committed here

- `rENA/man/*.Rd` — rENA's function documentation, used to track the API surface.
- `rENA_manifest.json` — the rENA exports the port is tracked against.

## What is **not** committed here

The full rENA sources (`rENA/R/`, `rENA/src/`, `rENA/tests/`, `rENA/inst/`) are
**not** in this repository. They are a large third-party GPL-3 tree, and vendoring
them would bloat the repo and duplicate an upstream project that has its own
release cadence.

Some docs and scripts refer to paths under `reference/rENA/R/...` or
`reference/rENA/tests/...`. Those paths only resolve if you place the sources
there yourself:

```bash
git clone https://gitlab.com/epistemic-analytics/qe-packages/rENA.git reference/rENA
```

`reference/rENA/` is git-ignored apart from the files listed above, so a clone
there will not be committed.

## You usually do not need the sources

For regenerating golden fixtures, the **installed rENA package is preferred and is
the authoritative oracle** — it is the released, compiled build:

```r
install.packages("rENA")   # or: remotes::install_gitlab("epistemic-analytics/qe-packages/rENA")
```

`scripts/generate_r_oracle.py` picks its oracle in this order:

| Order | Mode | Authoritative? |
|---|---|---|
| 1 | `installed-package` — the released, compiled rENA | **Yes** |
| 2 | `sourced-cpp` — sources here + Rcpp-compiled `ena.cpp` | **Yes** |
| 3 | `r-fallback` — sources here + pure-R rewrites of `ena.cpp` | **No** |

Mode 3 exists only so the generator can run without a C++ toolchain. It is **not**
a valid source of committed fixtures: those pure-R rewrites mirror ena-python's own
logic, so a fixture built from them would only show that ena-python agrees with a
re-implementation of itself — it could pass even if both sides shared a bug. The
generator refuses to write a fixture in mode 3 unless
`ENA_PYTHON_ALLOW_NONAUTHORITATIVE_ORACLE=1` is set, and
`tests/test_r_oracle_parity.py::test_fixture_provenance_is_authoritative` fails if a
non-authoritative fixture is ever committed.

Every fixture records the mode it came from under its `provenance` key.

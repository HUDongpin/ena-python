# Testing strategy

## Unit tests without R

Default `pytest` must pass on machines without R. These tests should cover:

- matrix utility examples with hand-computed results
- accumulation smoke tests
- normalization and SVD behavior
- object serialization
- web payload round trips

## R compatibility tests

R-dependent tests must be marked `rcompat` and skipped by default if R is unavailable.

Recommended workflow:

1. Install R and rENA dependencies locally.
2. Generate JSON fixtures with `scripts/generate_r_oracle.py`.
3. Commit small deterministic fixtures under `tests/fixtures/r_oracle/`.
4. Compare Python output to those fixtures with numeric tolerances.

Do not call R in production code.

## Porting order for tests

These live in the rENA source tree, which is **not** vendored in this repo — see
[`reference/README.md`](../reference/README.md) for how to obtain it. Paths below are
relative to an rENA checkout.

1. `tests/testthat/test.util.matrices.R`
2. `tests/testthat/test.ena.accumulations.R`
3. `tests/testthat/test.weighted.single.window.R`
4. `tests/testthat/test.ena.make.set.R`
5. `tests/testthat/test-rotation_matrix.R`
6. Plot tests after model parity is stable

## Fixture provenance

`scripts/generate_r_oracle.py` prefers the **installed rENA package** as its oracle,
which needs no source checkout:

```r
install.packages("rENA")
```

Every fixture records how it was produced under `provenance`, including whether the
oracle was authoritative (real compiled rENA) or the pure-R fallback. The generator
refuses to write a non-authoritative fixture, and
`test_fixture_provenance_is_authoritative` guards the committed one. See
[`reference/README.md`](../reference/README.md) for why that distinction matters.

# Codex prompt: build pyENA from rENA

You are working in a repository named `pyENA`. Your mission is to rewrite the uploaded R package `rENA` into a production-quality Python package named `pyENA` that is fast enough for website/backend use while preserving rENA's semantics.

## Context

The original R package source is available in `reference/rENA/`. Important directories:

- `reference/rENA/R/`: R implementation and public API wrappers *(not vendored; see `reference/README.md` to obtain the rENA sources)*
- `reference/rENA/src/ena.cpp`: Rcpp/Armadillo performance-critical primitives
- `reference/rENA/tests/testthat/`: expected behavior and edge cases *(not vendored)*
- `reference/rENA/man/`: generated R documentation for function semantics
- `reference/rENA/data/RS.data.rda` and `reference/rENA/inst/extdata/sample-data/`: small reference datasets

The Python scaffold is in `src/pyena/` and tests are in `tests/`.

## Product goal

Create a Python package that lets researchers and web services perform Epistemic Network Analysis without invoking R at runtime. The package should support a high-level workflow similar to rENA:

```python
from pyena import ena, accumulate, model

set_ = ena(
    data=df,
    codes=[...],
    units=[...],
    conversation=[...],
    metadata=[...],
    model="EndPoint",
    window="MovingStanzaWindow",
    window_size_back=1,
    window_size_forward=0,
    weight_by="binary",
)
```

It should also expose lower-level composable APIs:

```python
data = accumulate(df, units=[...], codes=[...], conversation=[...])
set_ = model(data, dimensions=2)
```

## Non-negotiable implementation rules

1. Preserve rENA semantics first, performance second.
2. Use R output as the oracle wherever behavior is unclear.
3. Do not silently change defaults from rENA unless a test and migration note justify the change.
4. Keep public Python APIs idiomatic: snake_case primary names, optional rENA-compatible aliases where useful.
5. Avoid R runtime dependencies in production code. R may only be used in compatibility fixture scripts/tests marked `rcompat`.
6. Prefer vectorized NumPy/Pandas implementations. Add optional Numba/Polars acceleration only behind clean backend boundaries.
7. Every implemented feature must include tests and docstring examples.
8. For web-development readiness, all core objects must be serializable to dictionaries/JSON-friendly forms.

## Migration priorities

### Phase 1: correctness core

Port and verify the primitives from `reference/rENA/src/ena.cpp`:

- `vector_to_ut` -> `pyena.matrix.vector_to_ut`
- `svector_to_ut` -> `pyena.matrix.adjacency_names`
- `rows_to_co_occurrences` -> `pyena.matrix.rows_to_co_occurrences`
- `ref_window_df` -> `pyena.matrix.ref_window_matrix`
- `fun_sphere_norm` and `fun_skip_sphere_norm` -> `pyena.normalize`
- `center_data_c` -> `pyena.rotation.center`

Write tests that compare against hard-coded small examples and then generated R fixtures.

### Phase 2: accumulation

Port `ena.accumulate.data`, `accumulate.data`, and `ena.accumulate.data.file` behavior:

- accept `units`, `conversation`, `codes`, optional `metadata`
- support `EndPoint`, `AccumulatedTrajectory`, and `SeparateTrajectory`
- support `MovingStanzaWindow` and `Conversation`
- support binary and weighted co-occurrence modes
- support masks
- preserve adjacency column order used by rENA: `code_1 & code_2`, `code_1 & code_3`, `code_2 & code_3`, ...

Use `reference/rENA/tests/testthat/test.ena.accumulations.R` and `test.weighted.single.window.R` as the behavioral guide.

### Phase 3: model/set construction

Port `ena.make.set`, `ena.svd`, `ena.rotate.by.mean`, generalized rotation, regression rotation, and node positioning:

- create `ENAData`, `ENASet`, and `ENARotationSet` Python dataclasses/Pydantic-compatible models
- compute line weights, centered points, rotation matrix, projected points, node positions, and eigenvalues
- match rENA numeric output within reasonable tolerances
- preserve metadata columns alongside matrices when appropriate

Use `reference/rENA/tests/testthat/test.ena.make.set.R`, `test-set_creator.R`, and `test-rotation_matrix.R`.

### Phase 4: plotting and web API

Port plotting semantics to Plotly and make them JSON/web friendly:

- `ena.plot`, `add_points`, `add_group`, `add_network`, `add_nodes`, `with_trajectory`
- expose `ENASet.to_dict()` / `to_json()` suitable for a frontend
- complete the FastAPI example in `examples/fastapi_service.py` and `src/pyena/web/api.py`

### Phase 5: performance

After parity tests pass:

- benchmark large CSV accumulation
- remove Python loops where feasible
- add optional Numba/Polars acceleration behind a backend interface
- target web request workflows where repeated calls reuse parsed schema/configuration

## How to work

For each feature:

1. Read the matching R source and tests.
2. Summarize the exact behavior in a short note under `docs/porting-notes/`.
3. Add or update Python tests.
4. Implement the smallest correct Python version.
5. Run `pytest` and `ruff check .`.
6. Add a migration-map entry in `docs/r_to_python_api_map.md` if the public API changed.

## Definition of done for an MVP

The MVP is complete when:

- `pytest` passes without R installed
- R compatibility tests pass when R and rENA dependencies are installed
- the high-level `ena()` example in `README.md` works
- `ENASet.to_dict()` returns frontend-friendly arrays and metadata
- at least one example FastAPI endpoint can accumulate and model uploaded tabular data
- benchmark results are documented in `docs/performance_strategy.md`

Start with matrix primitives and accumulation. Do not begin plotting until accumulation and model construction have parity tests.

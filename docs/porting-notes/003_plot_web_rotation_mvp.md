# Plot, Web, And Rotation MVP

This pass expands ena-python from core R oracle parity into a more usable package surface.

## Implemented

- `ENAData.to_dict()`, `ENASet.to_dict()`, and `ENARotationSet.to_dict()` now convert NaN and NumPy values into JSON-friendly Python values.
- `ENAData` carries `row_connection_counts` in addition to unit-level `connection_counts`.
- `ena_accumulate_data_file()` accepts a CSV path or DataFrame and maps rENA file-wrapper arguments to Python names.
- Plotly helpers cover the main rENA plotting families: base plot, points, groups, network edges, nodes, and trajectories.
- FastAPI exposes `/accumulate`, `/model`, `/ena`, and `/plot`.
- Advanced rotation families now have callable Python implementations: generalized means, regression, regression_2, and `rotation_h`.
- `cohens_d`, `ena_correlation`, and `ena_correlations` are available in `ena_python.stats`.

## Tests

- Ordinary pytest covers Plotly helper construction and JSON serialization.
- FastAPI endpoints are covered through `TestClient`.
- Stats and advanced rotations have smoke tests.
- Existing R oracle fixture tests continue to cover accumulation, `make_set`, SVD, mean rotation, rotation reuse, and zero-network centering.

## Remaining Parity Work

The advanced rotation family is not yet fixture-parity complete. The next oracle fixture expansion should add small R outputs for:

- `ena.rotate.by.generalized`
- `ena.rotate.by.hena.regression`
- `ena.rotate.by.hena.regression_2`
- `ena.rotation.h`
- plotting trace semantics where rENA behavior is user-visible

The current Plotly API is intentionally Pythonic and JSON-friendly rather than a byte-for-byte clone of the rENA plot object internals.

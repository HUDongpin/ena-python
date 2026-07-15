# Porting note 002: model, mean rotation, and node parity

This pass adds a generated R oracle fixture at
`tests/fixtures/r_oracle/generated/rena_parity_model.json`.

- The fixture is generated from the local `reference/rENA` source using
  `scripts/generate_r_oracle.py`. The script uses pure-R fallbacks for the
  Rcpp helpers when local compilation is unavailable.
- `ena.make.set` now follows rENA's line-weight normalization, center-vector
  handling, projected points, SVD rotation, least-squares node positions,
  centroids, variance, and rotation-set reuse for the covered fixture cases.
- Zero-network rows remain at the origin when `center_align_to_origin=True`,
  matching rENA's non-zero-only centering behavior.
- `rotate_by_mean` ports rENA's mean-difference and `orthogonal_svd` path,
  including the one-row group mean recycling behavior produced by R's
  `as.matrix(vector)` coercion.
- Generalized, regression, and hENA rotations were outside this pass. They have
  since been implemented (see `003_plot_web_rotation_mvp.md` and
  `docs/migration_guide.md`), so they no longer raise `NotImplementedError`, and
  they are now pinned to real compiled rENA 0.3.1 by
  `test_advanced_rotations_match_r_oracle` across 9 cases (numeric and categorical
  targets, x+y, and control variables).
- One deliberate divergence: with both `x_var` and `y_var`, `rotate_by_regression`
  returns a different y axis than rENA, because rENA fails to deflate there and
  produces near-collinear axes. See the `rotate_by_regression` docstring and
  `test_regression_xy_axes_are_orthogonal_unlike_rena`.

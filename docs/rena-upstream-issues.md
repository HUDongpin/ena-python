# Issues found in rENA 0.3.1

Notes recorded while porting [rENA](https://gitlab.com/epistemic-analytics/qe-packages/rENA) to Python. Each item is a place where rENA's behavior appears to differ from what its own code, comments, or documentation intend, and where pyENA therefore does something different on purpose.

This exists for two reasons: so pyENA users understand why a given result may not match rENA, and so the findings are in a form the rENA maintainers can check and act on if they wish.

Each is also tracked as an issue under the [`upstream-rena`](https://github.com/HUDongpin/pyENA/issues?q=label%3Aupstream-rena) label: [#1](https://github.com/HUDongpin/pyENA/issues/1), [#2](https://github.com/HUDongpin/pyENA/issues/2), [#3](https://github.com/HUDongpin/pyENA/issues/3), [#4](https://github.com/HUDongpin/pyENA/issues/4), [#5](https://github.com/HUDongpin/pyENA/issues/5). Those are **not** pyENA bugs; they live on this tracker because they came out of this port.

**Scope and caveats**

- Tested against **rENA 0.3.1** (the version pinned in [`reference/rENA_manifest.json`](../reference/rENA_manifest.json)) on R 4.4.2, `aarch64-apple-darwin20`, with the installed compiled package.
- These may already be fixed upstream, or may be deliberate choices whose rationale is not visible in the source. **They are reported as observations, not as accusations**; if any is intended behavior, the fault is in this document and I would like to correct it.
- Nothing here diminishes rENA. It is the reference implementation of ENA and the basis for this port; the great majority of it matched pyENA exactly, kernel for kernel. The two known **pyENA** defects found in the same effort were considerably worse — see [`CHANGELOG.md`](../CHANGELOG.md).
- Everything below is reproducible with the snippets given. Setup used by all of them:

```r
library(rENA)
rows <- data.frame(
  unit  = rep(paste0("U", 1:6), each = 4),
  conv  = rep(rep(c("c1", "c2"), each = 2), times = 6),
  grp   = rep(c("g1", "g2"), each = 12),
  score = rep(c(10, 20, 30, 40, 50, 60), each = 4),
  A = c(1,0,1,0, 0,1,1,1, 1,1,0,1, 0,0,1,0, 1,0,0,1, 0,1,1,0),
  B = c(0,1,1,1, 1,1,0,0, 0,1,1,0, 1,0,0,1, 0,1,1,0, 1,0,0,1),
  C = c(1,1,0,0, 1,0,1,0, 1,0,0,1, 0,1,1,1, 1,1,0,0, 0,0,1,1),
  D = c(0,0,1,1, 0,1,0,1, 0,1,1,0, 1,1,0,0, 0,0,1,1, 1,1,0,0),
  stringsAsFactors = FALSE)
acc <- ena.accumulate.data(
  units = rows[, "unit", drop = FALSE], conversation = rows[, "conv", drop = FALSE],
  metadata = rows[, c("grp", "score")], codes = rows[, c("A","B","C","D")],
  window.size.back = 2)
set <- ena.make.set(acc, dimensions = 2)

cosine <- function(m, i = 1, j = 2) {
  a <- m[, i]; b <- m[, j]
  sum(a * b) / (sqrt(sum(a * a)) * sqrt(sum(b * b)))
}
# ena.rotate.by.* return an ENARotationSet R6 object, which exposes $rotation
# (ena.make.set()$rotation$rotation.matrix is the data.table form; not the same slot).
rot <- function(r) as.matrix(r$rotation)
```

---

## 1. `ena.rotate.by.hena.regression` does not deflate the y axis

Tracked as [#1](https://github.com/HUDongpin/pyENA/issues/1).

**Severity: high — affects returned coordinates.**

Given both `x_var` and `y_var`, the two rotation axes come back strongly collinear, so the resulting "2D" projection is close to one-dimensional.

```r
reg <- ena.rotate.by.hena.regression(set, list(x_var = "V ~ score", y_var = "V ~ grp"))
gen <- ena.rotate.by.generalized(set, list(
  x_var = set$meta.data[, "score", drop = FALSE],
  y_var = set$meta.data[, "grp", drop = FALSE]))

cosine(rot(reg))   #> [1] 0.8116353       <- x and y are 81% collinear
cosine(rot(gen))   #> [1] -3.330669e-16   <- sibling function, same data: orthogonal
```

How collinear the axes come out depends on the data; 0.97 occurs on other datasets. That they are collinear at all is the point — an orthogonal pair would read ~1e-16, as `generalized` does.

The y axis is exactly what you get by regressing y on the **undeflated** points:

```r
y_alone <- ena.rotate.by.hena.regression(set, list(x_var = "V ~ grp"))
all.equal(abs(rot(reg)[, 2]), abs(rot(y_alone)[, 1]))   # TRUE
```

**Root cause.** `ena.rotate.by.regression.R:91` sets `V <- defA` to regress y on the x-deflated points. That assignment never takes effect. The call on line 99 is:

```r
v2_res <- with.ena.matrix(enaset$model$points.for.projection, {
  lm(formula(params$y_var));
});
```

and `with.ena.matrix` (`ena.rotate.by.regression.2.R:18-29`) binds its own `V`:

```r
with.ena.matrix <- function(data, expr, ...) {
  dot_args <- list(...);
  V <- NULL;
  if (length(dot_args) > 0 && !is.null(dot_args$V)) {
    V <- dot_args$V;          # only when a V = argument is passed
  } else {
    V <- as.matrix(data);     # otherwise: the raw points.for.projection
  }
  ...
```

No `V =` argument is passed, so `V` is rebound to the undeflated points and the caller's `V <- defA` is shadowed. The commented-out line immediately above the call (`ena.rotate.by.regression.R:98`) still shows the argument that would have made it work:

```r
# v2 <- with(enaset$model$points.for.projection, NULL, formula = y, V = V);
```

This reads as a refactor that dropped `V = V` rather than a design decision, for three reasons: the `V <- defA` line is left behind as dead code; `with.ena.matrix` still supports the `V =` argument; and the sibling `ena.rotate.by.generalized` deflates before its y-axis `gmr()` call on the same data (empirically, cosine 0).

Note that the *subsequent* deflation on line 130 (`defA <- defA - defA %*% v2 %*% t(v2)`) does use `v2`, so the SVD columns that complete the basis are deflated by both axes — it is only `v2` itself that is computed from undeflated data.

**Suggested fix:** pass the deflated matrix explicitly, e.g.
`with.ena.matrix(enaset$model$points.for.projection, { lm(formula(params$y_var)) }, V = defA)`.

**What pyENA does.** Deflates, giving orthogonal axes. The x axis matches rENA exactly. `pyena.rotation.rotate_by_regression` documents this, and `test_regression_xy_axes_are_orthogonal_unlike_rena` fails if rENA starts deflating — the signal for pyENA to match it again.

---

## 2. Regression axes are named after the first edge, not the predictor

Tracked as [#2](https://github.com/HUDongpin/pyENA/issues/2).

**Severity: low — cosmetic, but produces duplicate column names.**

```r
colnames(ena.rotate.by.hena.regression(set, list(x_var = "V ~ score"))$rotation)
#> "A & B_reg" "SVD2" "SVD3" "SVD4" "SVD5" "SVD6"
#     ^ expected "score_reg"

colnames(ena.rotate.by.hena.regression(set,
  list(x_var = "V ~ score", y_var = "V ~ grp"))$rotation)
#> "A & B_reg" "A & B_reg" "SVD3" "SVD4" "SVD5" "SVD6"
#     ^ both axes get the same name
```

**Root cause.** `ena.rotate.by.regression.R:75` derives the name with `xName <- all.vars(x)[2]`, which assumes `x` is a formula object. `params$x_var` is a character string, and `all.vars()` on a string returns nothing:

```r
all.vars("V ~ score")               # character(0)  -> all.vars(x)[2] is NA
all.vars(as.formula("V ~ score"))   # "V" "score"
```

`is.na(all.vars(x)[2])` is therefore always `TRUE`, and the branch falls back to `xName <- names(v1)[1]` — the first *edge* name. Line 121 does the same for `yName`, so with both axes the two columns collide.

**Suggested fix:** coerce first, e.g. `all.vars(as.formula(x))[2]`.

**What pyENA does.** Names the axis after the predictor (`score_reg`, `grp_reg`). Names are cosmetic and the vectors match, so pyENA does not reproduce this.

---

## 3. The documented `x_var` form raises an error

Tracked as [#3](https://github.com/HUDongpin/pyENA/issues/3).

**Severity: low — documentation/code mismatch.**

`ena.rotate.by.regression.R:11` documents:

> `x_var`: Regression formula for x direction, such as `"lm(formula=V ~ Condition + GameHalf + Condition : GameHalf)"`

Passing that form fails:

```r
ena.rotate.by.hena.regression(set, list(x_var = "lm(formula = V ~ score)"))
#> Error: attempt to set an attribute on NULL

ena.rotate.by.hena.regression(set, list(x_var = "V ~ score"))
#> works
```

**Root cause.** The code calls `formula(params$x_var)` (lines 55 and 100), which accepts a formula string such as `"V ~ score"` but not an `lm(...)` call wrapped in a string. The documentation appears to predate that change.

**Suggested fix:** update the docs to the plain formula form (or accept both).

**What pyENA does.** Accepts the plain formula form and documents it.

---

## 4. `ena.rotate.by.hena.regression_2` errors cryptically on rank-deficient input

Tracked as [#4](https://github.com/HUDongpin/pyENA/issues/4).

**Severity: low — diagnostics.**

`regression_2` fits `lm(score ~ V)`, needing `n_edges + 1` parameters. With fewer units than that, the fit is rank-deficient, R returns `NA` coefficients, and the error surfaces from an unrelated line:

```r
# 6 units, 4 codes -> 6 edges: 7 parameters for 6 observations
ena.rotate.by.hena.regression_2(set, list(x_var = "score ~ V"))
#> Error in if (norm_v1 != 0) { : missing value where TRUE/FALSE needed
```

With 7+ units and the same 4 codes it succeeds. The underlying situation is legitimate — you cannot fit 7 parameters to 6 observations — but `norm_v1 <- sqrt(sum(v1 * v1))` is `NA` when `v1` contains `NA`, and `if (norm_v1 != 0)` (`ena.rotate.by.regression.R:61`) then fails without explaining why.

**Suggested fix:** check for `NA` coefficients after the fit and report the rank deficiency directly.

**What pyENA does.** Different, and **not obviously better**: `numpy.linalg.lstsq` returns the minimum-norm solution for an underdetermined system, so pyENA returns a finite, unit-norm rotation vector where rENA errors. That answer is one of infinitely many, so rENA's loud failure is arguably the safer behavior. Do not read pyENA's output on rank-deficient input as more trustworthy; treat it as unconstrained. Improving this in pyENA is tracked as future work.

---

## 5. `ena.rotation.h` emits a `data.table` warning on every call

Tracked as [#5](https://github.com/HUDongpin/pyENA/issues/5).

**Severity: trivial — noise.**

```r
ena.rotation.h(set, list(x_var = "grp"))
#> Warning: Both 'value_vars' and '..value_vars' exist in calling scope.
#> Please remove the '..value_vars' variable in calling scope for clarity.
```

The rotation itself is correct — pyENA matches it exactly, including with `control_vars` — but every call warns. This is the `data.table` `..var` prefix colliding with a local of the same name inside `ena.rotation.h`.

**Suggested fix:** rename the local, or index with `.SDcols`.

**What pyENA does.** Nothing to reproduce; noted only for anyone comparing console output.

---

## What matched

For balance, the following were checked against real compiled rENA 0.3.1 and agree to within `1e-7`–`1e-10`, in most cases exactly:

- `vector_to_ut`, `rows_to_co_occurrences`, `ref_window_df` (including infinite forward/back windows), `fun_sphere_norm`, `fun_skip_sphere_norm`, `center_data_c`, `lws_lsq_positions`, `ena_correlation`
- EndPoint / Conversation / AccumulatedTrajectory / SeparateTrajectory accumulation and full models
- SVD rotation, projected points, node positions, centroids, center vector, `variance`, `eigenvalues`
- `ena.rotate.by.mean`, `ena.rotate.by.generalized` (numeric and categorical targets, and x+y), `ena.rotate.by.hena.regression` (x axis), `ena.rotate.by.hena.regression_2`, `ena.rotation.h` (including control variables)

See [`tests/test_r_oracle_parity.py`](../tests/test_r_oracle_parity.py) and the [README parity table](../README.md#parity-with-rena).

## Reporting upstream

These have not been filed with the rENA maintainers. If you have a GitLab account on
[epistemic-analytics/qe-packages/rENA](https://gitlab.com/epistemic-analytics/qe-packages/rENA)
and want to report them, items 1–3 are the ones worth their time; each snippet above is self-contained.

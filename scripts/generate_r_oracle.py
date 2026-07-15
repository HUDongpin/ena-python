from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from pyena.compat.r_bridge import run_r_script

R_SCRIPT_TEMPLATE = r"""
suppressPackageStartupMessages({
  library(data.table)
  library(jsonlite)
  library(R6)
})

source_dir <- "__SOURCE_DIR__"

require_package <- function(pkg) {
  if (!requireNamespace(pkg, quietly = TRUE)) {
    stop(sprintf("Package '%s' is required for oracle generation.", pkg), call. = FALSE)
  }
}

install_rcpp_fallbacks <- function() {
  combn_c2 <<- function(n) {
    out <- matrix(0, nrow = 2, ncol = n * (n - 1) / 2)
    col <- 1
    for (i in seq_len(n)) {
      if (i < n) {
        for (j in seq.int(i + 1, n)) {
          out[1, col] <- i - 1
          out[2, col] <- j - 1
          col <- col + 1
        }
      }
    }
    out
  }

  merge_columns_c <<- function(df, cols, sep = "::") {
    apply(as.data.frame(df)[, as.character(cols), drop = FALSE], 1, paste, collapse = sep)
  }

  vector_to_ut <<- function(v) {
    v <- as.numeric(v)
    out <- numeric(length(v) * (length(v) - 1) / 2)
    s <- 1
    for (i in seq.int(2, length(v))) {
      for (j in seq_len(i - 1)) {
        out[s] <- v[j] * v[i]
        s <- s + 1
      }
    }
    out
  }

  svector_to_ut <<- function(v) {
    out <- character(length(v) * (length(v) - 1) / 2)
    s <- 1
    for (i in seq.int(2, length(v))) {
      for (j in seq_len(i - 1)) {
        out[s] <- paste(v[j], v[i], sep = " & ")
        s <- s + 1
      }
    }
    out
  }

  rows_to_co_occurrences <<- function(df, binary = TRUE) {
    m <- as.matrix(df)
    out <- t(apply(m, 1, vector_to_ut))
    if (is.null(dim(out))) out <- matrix(out, nrow = nrow(m))
    if (binary) out[out > 0] <- 1
    out
  }

  ref_window_df <<- function(df, windowSize = 1, windowForward = 0, binary = TRUE) {
    m <- as.matrix(df)
    out <- matrix(0, nrow = nrow(m), ncol = ncol(m) * (ncol(m) - 1) / 2)
    window_back <- if (is.infinite(windowSize)) .Machine$integer.max else as.integer(windowSize)
    window_forward <- if (is.infinite(windowForward)) nrow(m) else as.integer(windowForward)
    for (row_index in seq_len(nrow(m))) {
      row <- row_index - 1
      earliest_row <- 0
      last_row <- row
      if (window_back == .Machine$integer.max || window_back == -.Machine$integer.max) {
        earliest_row <- 0
      } else if (window_back == 0) {
        earliest_row <- row
      } else if (row - (window_back - 1) >= 0) {
        earliest_row <- row - (window_back - 1)
      }
      if (is.infinite(windowForward) || row + window_forward >= nrow(m)) {
        last_row <- nrow(m) - 1
      } else if (window_forward > 0 && row + window_forward <= nrow(m) - 1) {
        last_row <- row + window_forward
      }
      curr_rows <- m[seq.int(earliest_row + 1, last_row + 1), , drop = FALSE]
      to_ut <- vector_to_ut(colSums(curr_rows))
      curr_row_count <- nrow(curr_rows)
      if (curr_row_count > 0 && window_back > 1 && row - 1 >= 0) {
        head_rows <- curr_row_count - 1 - window_forward
        if (head_rows > 0) {
          to_ut <- to_ut - vector_to_ut(colSums(curr_rows[seq_len(head_rows), , drop = FALSE]))
        }
      }
      if (curr_row_count > 0 && window_forward > 0 && last_row <= nrow(m) - 1) {
        tail_rows_to_use <- last_row - row
        if (tail_rows_to_use > 0) {
          to_ut <- to_ut - vector_to_ut(colSums(utils::tail(curr_rows, tail_rows_to_use)))
        }
      }
      out[row_index, ] <- to_ut
    }
    if (binary) out[out > 0] <- 1
    as.data.frame(out)
  }

  ref_window_lag <<- function(df, windowSize = 0L, binary = TRUE) {
    m <- as.matrix(df)
    out <- matrix(0, nrow = nrow(m), ncol = ncol(m))
    for (row_index in seq_len(nrow(m))) {
      row <- row_index - 1
      start <- max(0, row - (windowSize - 1))
      out[row_index, ] <- colSums(m[seq.int(start + 1, row + 1), , drop = FALSE])
    }
    as.data.frame(out)
  }

  fun_sphere_norm <<- function(dfM) {
    m <- as.matrix(dfM)
    out <- matrix(0, nrow = nrow(m), ncol = ncol(m))
    for (row in seq_len(nrow(m))) {
      root <- sqrt(sum(m[row, ] ^ 2))
      if (root > 0) out[row, ] <- m[row, ] / root
    }
    out
  }

  fun_skip_sphere_norm <<- function(dfM) {
    m <- as.matrix(dfM)
    largest <- max(apply(m, 1, function(row) sqrt(sum(row ^ 2))))
    m / largest
  }

  center_data_c <<- function(values) {
    m <- as.matrix(values)
    sweep(m, 2, colMeans(m), "-")
  }

  triIndices <<- function(len, row = -1) {
    first <- integer()
    second <- integer()
    for (i in seq.int(2, len)) {
      for (j in seq_len(i - 1)) {
        first <- c(first, j - 1)
        second <- c(second, i - 1)
      }
    }
    if (row == 0) return(matrix(first, nrow = 1))
    if (row == 1) return(matrix(second, nrow = 1))
    rbind(first, second)
  }

  lws_lsq_positions <<- function(adjMats, t, numDims) {
    adjMats <- as.matrix(adjMats)
    t <- as.matrix(t)
    upperTriSize <- ncol(adjMats)
    numNodes <- ceiling(sqrt(2 * upperTriSize)) ^ 2 - (2 * upperTriSize)
    weights <- matrix(0, nrow = nrow(adjMats), ncol = numNodes)
    for (k in seq_len(nrow(adjMats))) {
      z <- 1
      for (x in seq.int(0, numNodes - 2)) {
        for (y in seq.int(0, x)) {
          weights[k, x + 2] <- weights[k, x + 2] + (0.5 * adjMats[k, z])
          weights[k, y + 1] <- weights[k, y + 1] + (0.5 * adjMats[k, z])
          z <- z + 1
        }
      }
    }
    for (k in seq_len(nrow(weights))) {
      length <- sum(abs(weights[k, ]))
      if (length < 0.0001) length <- 0.0001
      weights[k, ] <- weights[k, ] / length
    }
    ssX <- matrix(0, nrow = numDims, ncol = numNodes)
    ssA <- t(weights) %*% weights
    for (i in seq_len(numDims)) {
      ssb <- t(weights) %*% t[, i]
      ssX[i, ] <- tryCatch(solve(ssA, ssb), error = function(e) solve(ssA + diag(1e-10, nrow(ssA)), ssb))
    }
    list(nodes = t(ssX), centroids = t(ssX %*% t(weights)), weights = weights, points = t)
  }
}

# Oracle selection, in descending order of authority:
#
#   1. installed-package : the released, compiled rENA. Authoritative.
#   2. sourced-cpp       : vendored rENA R sources + Rcpp-compiled ena.cpp. Authoritative.
#   3. r-fallback        : vendored R sources + pure-R transliterations of ena.cpp.
#                          NOT authoritative -- the transliterations mirror pyENA's own
#                          logic, so a fixture built this way can only prove that pyENA
#                          agrees with a re-implementation of itself. Fixtures generated
#                          in this mode are refused for committing unless
#                          PYENA_ALLOW_NONAUTHORITATIVE_ORACLE=1.
load_installed_rena <- function() {
  if (!requireNamespace("rENA", quietly = TRUE)) return(NULL)
  suppressPackageStartupMessages(library(rENA))
  list(mode = "installed-package",
       rena_version = as.character(utils::packageVersion("rENA")),
       authoritative = TRUE)
}

load_reference_rena <- function(source_dir) {
  if (!dir.exists(source_dir)) return(NULL)
  # `reference/rENA` must carry real sources, not just man/ pages.
  if (!file.exists(file.path(source_dir, "R", "ena.make.set.R"))) return(NULL)
  for (pkg in c("data.table", "R6")) require_package(pkg)

  # ena.cpp is C++ (Rcpp/RcppArmadillo); it does not require a Fortran compiler.
  # Gating on gfortran silently forced most machines onto the non-authoritative
  # pure-R fallback, so only the packages that actually matter are checked here.
  mode <- "r-fallback"
  if (requireNamespace("Rcpp", quietly = TRUE) && requireNamespace("RcppArmadillo", quietly = TRUE)) {
    compiled <- tryCatch({
      Rcpp::sourceCpp(file.path(source_dir, "src", "ena.cpp"), env = globalenv(), verbose = FALSE)
      TRUE
    }, error = function(e) FALSE)
    if (isTRUE(compiled)) mode <- "sourced-cpp" else install_rcpp_fallbacks()
  } else {
    install_rcpp_fallbacks()
  }

  r_files <- c(
    "rENA.R", "utils.classes.R", "utils.R", "utils.matrix.R",
    "ENArotation.set.R", "ENAdata.R", "accumulate.data.R",
    "ena.accumulate.data.R", "ena.set.R", "center.projection.R",
    "ena.svd.R", "ena.rotate.by.mean.R", "lws.positions.sq.R",
    "ena.make.set.R"
  )
  for (file in r_files) source(file.path(source_dir, "R", file), local = globalenv())

  version <- tryCatch({
    desc <- read.dcf(file.path(source_dir, "DESCRIPTION"))
    if ("Version" %in% colnames(desc)) as.character(desc[1, "Version"]) else NA_character_
  }, error = function(e) NA_character_)

  list(mode = mode, rena_version = version, authoritative = identical(mode, "sourced-cpp"))
}

oracle <- load_installed_rena()
if (is.null(oracle)) oracle <- load_reference_rena(source_dir)
if (is.null(oracle)) {
  stop(paste0(
    "No rENA oracle available. Install the rENA package, or place full rENA ",
    "sources (R/ and src/) at ", source_dir, "."
  ), call. = FALSE)
}

plain_df <- function(x) {
  out <- as.data.frame(x, stringsAsFactors = FALSE)
  rownames(out) <- NULL
  for (name in names(out)) {
    col <- out[[name]]
    if (is.factor(col)) out[[name]] <- as.character(col) else {
      attributes(col) <- NULL
      out[[name]] <- col
    }
  }
  out
}

toy <- data.frame(
  unit = c("u1", "u1", "u1", "u1", "u2", "u2", "u2", "u3", "u3"),
  conv = c("c1", "c1", "c1", "c2", "c1", "c1", "c2", "c1", "c2"),
  group = c("g1", "g1", "g1", "g1", "g2", "g2", "g2", "g1", "g1"),
  score = c(10, 10, 10, 10, 20, 20, 20, 30, 30),
  A = c(1, 0, 0, 1, 1, 0, 0, 1, 0),
  B = c(0, 1, 0, 1, 0, 1, 1, 1, 0),
  C = c(0, 0, 1, 0, 1, 1, 0, 0, 1),
  stringsAsFactors = FALSE
)
codes <- c("A", "B", "C")

golden_accumulation <- function(rows, model = "EndPoint", window = "MovingStanzaWindow") {
  accum <- ena.accumulate.data(
    units = rows[, c("unit"), drop = FALSE],
    conversation = rows[, c("conv"), drop = FALSE],
    metadata = rows[, c("group", "score"), drop = FALSE],
    codes = rows[, codes, drop = FALSE],
    model = model,
    window = window,
    window.size.back = 2,
    as.list = TRUE
  )
  out <- list(
    connection_counts = plain_df(accum$connection.counts),
    row_connection_counts = plain_df(accum$model$row.connection.counts),
    unit_labels = accum$model$unit.labels,
    meta_data = plain_df(accum$meta.data)
  )
  if (!is.null(accum$trajectories)) out$trajectories <- plain_df(accum$trajectories)
  out
}

golden_model <- function(accum, ...) {
  set <- ena.make.set(accum, dimensions = 2, ...)
  list(
    line_weights = plain_df(set$line.weights),
    points_for_projection = plain_df(set$model$points.for.projection),
    points = plain_df(set$points),
    rotation_matrix = plain_df(set$rotation$rotation.matrix),
    eigenvalues = unname(set$rotation$eigenvalues),
    center_vec = unname(set$rotation$center.vec),
    nodes = plain_df(set$rotation$nodes),
    centroids = plain_df(set$model$centroids),
    variance = unname(set$model$variance)
  )
}

base_accum <- ena.accumulate.data(
  units = toy[, c("unit"), drop = FALSE],
  conversation = toy[, c("conv"), drop = FALSE],
  metadata = toy[, c("group", "score"), drop = FALSE],
  codes = toy[, codes, drop = FALSE],
  window.size.back = 2,
  as.list = TRUE
)
base_model <- golden_model(base_accum)
mean_model <- golden_model(
  base_accum,
  rotation.by = ena.rotate.by.mean,
  rotation.params = list(base_accum$meta.data$group == "g1", base_accum$meta.data$group == "g2")
)

zero_accum <- base_accum
zero_units <- zero_accum$connection.counts$ENA_UNIT[c(1)]
zero_accum$connection.counts[zero_accum$connection.counts$ENA_UNIT %in% zero_units, c("A & B", "A & C", "B & C")] <- 0
zero_model_true <- golden_model(zero_accum, center.align.to.origin = TRUE)
zero_model_false <- golden_model(zero_accum, center.align.to.origin = FALSE)

reuse_accum <- ena.accumulate.data(
  units = toy[, c("group"), drop = FALSE],
  conversation = toy[, c("conv"), drop = FALSE],
  metadata = toy[, c("score"), drop = FALSE],
  codes = toy[, codes, drop = FALSE],
  window.size.back = 2,
  as.list = TRUE
)
reuse_model <- golden_model(reuse_accum, rotation.set = ena.make.set(base_accum, dimensions = 2)$rotation)

# --- Rank-3+ dataset -------------------------------------------------------
# The toy above has 3 units, so its centered networks have rank 2 and the third
# singular value is ~0. That degeneracy makes "normalize over 2 dims" and
# "normalize over all dims" numerically identical, which hid a real variance
# defect. This dataset (6 units x 4 codes -> 6 dimensions) is full-rank enough
# that the two differ, so `variance` and `eigenvalues` are actually pinned.
rank3 <- data.frame(
  unit = rep(paste0("U", 1:6), each = 6),
  conv = rep(rep(c("c1", "c2"), each = 3), times = 6),
  # Constant within each unit: a group label is a property of the unit, and a
  # metadata column that varies inside a unit is (correctly) dropped with a warning.
  grp = rep(c("g1", "g2"), times = 3, each = 6),
  A = c(1,0,1,0,1,1, 0,1,1,1,0,0, 1,1,0,1,0,1, 0,0,1,0,1,0, 1,0,0,1,1,0, 0,1,1,0,0,1),
  B = c(0,1,1,1,0,0, 1,1,0,0,1,1, 0,1,1,0,1,0, 1,0,0,1,0,1, 0,1,1,0,0,1, 1,0,0,1,1,0),
  C = c(1,1,0,0,1,0, 1,0,1,0,1,0, 1,0,0,1,1,1, 0,1,1,1,0,0, 1,1,0,0,1,1, 0,0,1,1,0,1),
  D = c(0,0,1,1,0,1, 0,1,0,1,0,1, 0,1,1,0,0,1, 1,1,0,0,1,0, 0,0,1,1,0,1, 1,1,0,0,1,0),
  stringsAsFactors = FALSE
)
codes4 <- c("A", "B", "C", "D")

rank3_accum <- ena.accumulate.data(
  units = rank3[, c("unit"), drop = FALSE],
  conversation = rank3[, c("conv"), drop = FALSE],
  metadata = rank3[, c("grp"), drop = FALSE],
  codes = rank3[, codes4, drop = FALSE],
  window.size.back = 2,
  as.list = TRUE
)
rank3_set <- ena.make.set(rank3_accum, dimensions = 2)
rank3_model <- list(
  line_weights = plain_df(rank3_set$line.weights),
  points_for_projection = plain_df(rank3_set$model$points.for.projection),
  points = plain_df(rank3_set$points),
  rotation_matrix = plain_df(rank3_set$rotation$rotation.matrix),
  eigenvalues = unname(rank3_set$rotation$eigenvalues),
  center_vec = unname(rank3_set$rotation$center.vec),
  nodes = plain_df(rank3_set$rotation$nodes),
  centroids = plain_df(rank3_set$model$centroids),
  variance = unname(rank3_set$model$variance)
)

# --- Model-level fixtures for the Conversation window and both trajectory models --
# The accumulate-level fixtures below were generated but never asserted. Carrying the
# modeled output too pins the whole pipeline (normalize -> center -> rotate -> project)
# for these model types, not just the co-occurrence counts.
model_for <- function(model = "EndPoint", window = "MovingStanzaWindow") {
  a <- ena.accumulate.data(
    units = toy[, c("unit"), drop = FALSE],
    conversation = toy[, c("conv"), drop = FALSE],
    metadata = toy[, c("group", "score"), drop = FALSE],
    codes = toy[, codes, drop = FALSE],
    model = model, window = window, window.size.back = 2, as.list = TRUE
  )
  s <- ena.make.set(a, dimensions = 2)
  out <- list(
    line_weights = plain_df(s$line.weights),
    points = plain_df(s$points),
    rotation_matrix = plain_df(s$rotation$rotation.matrix),
    eigenvalues = unname(s$rotation$eigenvalues),
    center_vec = unname(s$rotation$center.vec),
    nodes = plain_df(s$rotation$nodes),
    centroids = plain_df(s$model$centroids),
    variance = unname(s$model$variance),
    unit_labels = a$model$unit.labels
  )
  if (!is.null(a$trajectories)) out$trajectories <- plain_df(a$trajectories)
  out
}

# --- Rotation fixtures ------------------------------------------------------
# 8 units x 4 codes, with a unit-level categorical (grp) and numeric (score)
# covariate. gmr() branches on whether the target is numeric, so both are needed.
rot_rows <- data.frame(
  unit  = rep(paste0("U", 1:8), each = 6),
  conv  = rep(rep(c("c1", "c2"), each = 3), times = 8),
  grp   = rep(c("g1", "g2"), each = 24),
  score = rep(seq(10, 80, by = 10), each = 6),
  A = c(1,0,1,0,1,1, 0,1,1,1,0,0, 1,1,0,1,0,1, 0,0,1,0,1,0,
        1,0,0,1,1,0, 0,1,1,0,0,1, 1,1,0,0,1,0, 0,0,1,1,0,1),
  B = c(0,1,1,1,0,0, 1,1,0,0,1,1, 0,1,1,0,1,0, 1,0,0,1,0,1,
        0,1,1,0,0,1, 1,0,0,1,1,0, 0,1,0,1,0,1, 1,0,1,0,1,0),
  C = c(1,1,0,0,1,0, 1,0,1,0,1,0, 1,0,0,1,1,1, 0,1,1,1,0,0,
        1,1,0,0,1,1, 0,0,1,1,0,1, 1,0,1,0,0,1, 0,1,0,1,1,0),
  D = c(0,0,1,1,0,1, 0,1,0,1,0,1, 0,1,1,0,0,1, 1,1,0,0,1,0,
        0,0,1,1,0,1, 1,1,0,0,1,0, 0,1,1,1,0,0, 1,0,0,1,0,1),
  stringsAsFactors = FALSE
)
rot_codes <- c("A", "B", "C", "D")
rot_accum <- ena.accumulate.data(
  units = rot_rows[, c("unit"), drop = FALSE],
  conversation = rot_rows[, c("conv"), drop = FALSE],
  metadata = rot_rows[, c("grp", "score"), drop = FALSE],
  codes = rot_rows[, rot_codes, drop = FALSE],
  window.size.back = 2, as.list = TRUE
)
rot_base <- ena.make.set(rot_accum, dimensions = 2)

rotation_case <- function(fn, params) {
  res <- tryCatch(fn(rot_base, params), error = function(e) NULL)
  if (is.null(res)) return(NULL)
  rm_ <- if (!is.null(res$rotation.matrix)) res$rotation.matrix else res$rotation
  list(colnames = colnames(rm_), values = plain_df(as.data.frame(unname(as.data.frame(rm_)))))
}

rotations <- list(
  generalized_score  = rotation_case(ena.rotate.by.generalized,
                         list(x_var = rot_base$meta.data[, "score", drop = FALSE])),
  generalized_grp    = rotation_case(ena.rotate.by.generalized,
                         list(x_var = rot_base$meta.data[, "grp", drop = FALSE])),
  generalized_xy     = rotation_case(ena.rotate.by.generalized,
                         list(x_var = rot_base$meta.data[, "score", drop = FALSE],
                              y_var = rot_base$meta.data[, "grp", drop = FALSE])),
  regression_score   = rotation_case(ena.rotate.by.hena.regression, list(x_var = "V ~ score")),
  regression_grp     = rotation_case(ena.rotate.by.hena.regression, list(x_var = "V ~ grp")),
  # Recorded but NOT asserted column-for-column: rENA regresses y on the *undeflated*
  # points here, so its x and y axes come out ~97% collinear. See
  # test_regression_xy_axes_are_orthogonal_unlike_rena.
  regression_xy      = rotation_case(ena.rotate.by.hena.regression,
                         list(x_var = "V ~ score", y_var = "V ~ grp")),
  regression2_score  = rotation_case(ena.rotate.by.hena.regression_2, list(x_var = "score ~ V")),
  rotation_h_grp     = rotation_case(ena.rotation.h, list(x_var = "grp")),
  rotation_h_score   = rotation_case(ena.rotation.h, list(x_var = "score")),
  rotation_h_ctrl    = rotation_case(ena.rotation.h, list(x_var = "grp", control_vars = c("score")))
)

payload <- list(
  provenance = list(
    oracle_mode = oracle$mode,
    authoritative = oracle$authoritative,
    rena_version = oracle$rena_version,
    r_version = R.version.string,
    platform = R.version$platform,
    generated_at = format(Sys.time(), "%Y-%m-%dT%H:%M:%S%z"),
    data_table_version = as.character(utils::packageVersion("data.table"))
  ),
  input = plain_df(toy),
  codes = codes,
  models = list(
    conversation = model_for(window = "Conversation"),
    accumulated_trajectory = model_for(model = "AccumulatedTrajectory"),
    separate_trajectory = model_for(model = "SeparateTrajectory")
  ),
  rotations = list(
    input = plain_df(rot_rows),
    codes = rot_codes,
    cases = rotations
  ),
  rank3 = list(
    input = plain_df(rank3),
    codes = codes4,
    model = rank3_model
  ),
  accumulate = list(
    endpoint = golden_accumulation(toy),
    conversation = golden_accumulation(toy, window = "Conversation"),
    accumulated_trajectory = golden_accumulation(toy, model = "AccumulatedTrajectory"),
    separate_trajectory = golden_accumulation(toy, model = "SeparateTrajectory")
  ),
  model = base_model,
  mean_model = mean_model,
  zero_networks = list(
    zero_units = zero_units,
    center_true = zero_model_true,
    center_false = zero_model_false
  ),
  rotation_reuse = reuse_model
)

cat(jsonlite::toJSON(payload, dataframe = "rows", digits = 15, auto_unbox = TRUE, null = "null"))
"""


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    source_dir = repo_root / "reference" / "rENA"
    out_dir = repo_root / "tests" / "fixtures" / "r_oracle" / "generated"
    out_dir.mkdir(parents=True, exist_ok=True)
    script = R_SCRIPT_TEMPLATE.replace('"__SOURCE_DIR__"', json.dumps(str(source_dir)))
    result = run_r_script(script, cwd=repo_root)

    provenance = result.get("provenance", {})
    if not provenance.get("authoritative", False):
        message = (
            f"Oracle mode {provenance.get('oracle_mode')!r} is NOT authoritative: the pure-R\n"
            "fallback re-implements ena.cpp along the same lines as pyENA, so a fixture built\n"
            "from it cannot prove parity with rENA -- only that pyENA agrees with a\n"
            "re-implementation of itself.\n\n"
            "Install the rENA package (recommended), or provide full rENA sources with a\n"
            "working C++ toolchain. Set PYENA_ALLOW_NONAUTHORITATIVE_ORACLE=1 to override."
        )
        if os.environ.get("PYENA_ALLOW_NONAUTHORITATIVE_ORACLE") != "1":
            raise SystemExit(message)
        print(f"WARNING: {message}", file=sys.stderr)

    out_file = out_dir / "rena_parity_model.json"
    out_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        f"{out_file}\n"
        f"  oracle        : {provenance.get('oracle_mode')} "
        f"(authoritative={provenance.get('authoritative')})\n"
        f"  rENA version  : {provenance.get('rena_version')}\n"
        f"  R version     : {provenance.get('r_version')}\n"
        f"  platform      : {provenance.get('platform')}"
    )


if __name__ == "__main__":
    main()

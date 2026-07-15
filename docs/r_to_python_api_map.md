# rENA to pyENA API map

Generated from the uploaded `rENA` package `NAMESPACE` and R source files. Use this as the living migration checklist.

| rENA API | Proposed pyENA API | Source | Status | R arguments |
|---|---|---|---|---|
| `ENARotationSet` | `ENARotationSet` | `` | rotation matrix/node/center serialization | `` |
| `ENAdata` | `ENAData` | `` | dataclass scaffold | `` |
| `ENAplot` | `ENAPlot` | `` | not ported | `` |
| `ENAset` | `ENASet` | `` | model outputs + JSON serialization | `` |
| `accumulate` | `accumulate` | `R/piped.R` | initial implementation | `x, units = rENA::units(x), codes = rENA::codes(x), horizon = rENA::horizon(x), ..., ordered = FALSE, binary = TRUE` |
| `add_group` | `add_group` | `R/utils.plot.R` | Plotly MVP, JSON smoke-covered | `x, wh = NULL, ...` |
| `add_network` | `add_network` | `R/utils.plot.R` | Plotly MVP, JSON smoke-covered | `x, wh = NULL, ..., with.mean = F, edge.multiplier = 1, colors = NULL` |
| `add_nodes` | `add_nodes` | `R/utils.plot.R` | Plotly MVP, JSON smoke-covered | `x, ..., return_plot = FALSE` |
| `add_points` | `add_points` | `R/utils.plot.R` | Plotly MVP, JSON smoke-covered | `x, wh = NULL, ..., colors = NULL` |
| `add_trajectory` | `with_trajectory` | `R/utils.plot.R` | Plotly MVP, JSON smoke-covered | `x, wh = NULL, ..., name = "plot"` |
| `as.ena.co.occurrence` | `as_ena_co_occurrence` | `R/utils.classes.R` | not ported | `x` |
| `as.ena.matrix` | `as_ena_matrix` | `R/utils.classes.R` | not ported | `x, new.class = NULL` |
| `as.ena.metadata` | `as_ena_metadata` | `R/utils.classes.R` | not ported | `x` |
| `as.qe.code` | `as_qe_code` | `R/qedata_classes.R` | not ported | `x` |
| `as.qe.data` | `as_qe_data` | `R/qedata_classes.R` | not ported | `x` |
| `as.qe.horizon` | `as_qe_horizon` | `R/qedata_classes.R` | not ported | `x` |
| `as.qe.metadata` | `as_qe_metadata` | `R/qedata_classes.R` | not ported | `x` |
| `as.qe.unit` | `as_qe_unit` | `R/qedata_classes.R` | not ported | `x` |
| `as_trajectory` | `as_trajectory` | `R/utils.R` | not ported | `x, by = x$`_function.params`$conversation[1], model = c("AccumulatedTrajectory", "SeperateTrajectory"), ...` |
| `center` | `center` | `R/piped.R` | initial implementation | `x, add.meta = TRUE` |
| `check_range` | `check_range` | `R/utils.plot.R` | not ported | `x` |
| `clear` | `clear` | `R/utils.plot.R` | not ported | `x, wh = seq(x$plots)` |
| `codes` | `codes` | `R/qedata_define.R` | not ported | `x, ...` |
| `combn_c2` | `combn_c2` | `R/RcppExports.R` | not ported | `n` |
| `connection.matrix` | `connection_matrix` | `R/connection.matrix.R` | initial implementation | `x` |
| `define` | `define` | `R/qedata_define.R` | not ported | `x, metadata_cols = find_meta_cols(x), codes_cols = find_binary_cols(x), horizon_cols = NULL, units_cols = NULL` |
| `directed_node_positions` | `directed_node_positions` | `R/RcppExports.R` | not ported | `line_weights, points, numDims` |
| `directed_node_positions_with_ground_response_added` | `directed_node_positions_with_ground_response_added` | `R/RcppExports.R` | not ported | `line_weights, points, numDims` |
| `ena` | `ena` | `R/ena.R` | initial implementation | `data, codes, units, conversation, metadata = NULL, model = c("EndPoint", "AccumulatedTrajectory", "SeparateTrajectory"), weight.by = "binary", window = c("MovingStanzaWindow", "Con` |
| `ena.accumulate.data` | `ena_accumulate_data` | `R/ena.accumulate.data.R` | separate-frame + conversation-window parity | `units = NULL, conversation = NULL, codes = NULL, metadata = NULL, model = c("EndPoint", "AccumulatedTrajectory", "SeparateTrajectory"), weight.by = "binary", window = c("MovingStan` |
| `ena.accumulate.data.file` | `ena_accumulate_data_file` | `R/ena.accumulate.data.file.R` | CSV/DataFrame wrapper implemented | `file, units.used = NULL, conversations.used = NULL, units.by, conversations.by, codes = NULL, ...` |
| `ena.conversations` | `ena_conversations` | `` | not ported | `` |
| `ena.correlations` | `ena_correlations` | `R/ena.correlations.R` | implemented, smoke-covered | `enaset, dims = c(1:2)` |
| `ena.group` | `ena_group` | `R/ena.group.R` | not ported | `enaset = NULL, by = NULL, method = mean, names = as.vector(unique(by))` |
| `ena.make.set` | `ena_make_set` | `R/ena.make.set.R` | SVD/mean/node parity fixture coverage | `enadata, dimensions = 2, norm.by = fun_sphere_norm, rotation.by = ena.svd, rotation.params = NULL, rotation.set = NULL, endpoints.only = TRUE, center.align.to.origin = TRUE, node.p` |
| `ena.plot` | `ena_plot` | `R/ena.plot.R` | Plotly MVP, JSON smoke-covered | `enaset, title = "ENA Plot", dimension.labels = c("",""), font.size = 10, font.color = "#000000", font.family = c("Arial", "Courier New", "Times New Roman"), scale.to = "network", #` |
| `ena.plot.group` | `ena_plot_group` | `R/ena.plot.group.R` | Plotly MVP, JSON smoke-covered | `enaplot, points = NULL, method = "mean", labels = NULL, colors = default.colors[1], shape = c("square", "triangle-up", "diamond", "circle"), confidence.interval = c("none", "crossh` |
| `ena.plot.network` | `ena_plot_network` | `` | Plotly MVP, JSON smoke-covered | `` |
| `ena.plot.points` | `ena_plot_points` | `` | Plotly MVP, JSON smoke-covered | `` |
| `ena.plot.trajectory` | `ena_plot_trajectory` | `` | Plotly MVP, JSON smoke-covered | `` |
| `ena.plotter` | `ena_plotter` | `` | not ported | `` |
| `ena.rotate.by.generalized` | `ena_rotate_by_generalized` | `` | implemented MVP, smoke-covered; needs R oracle expansion | `` |
| `ena.rotate.by.hena.regression` | `ena_rotate_by_hena_regression` | `` | implemented MVP, smoke-covered; needs R oracle expansion | `` |
| `ena.rotate.by.hena.regression_2` | `ena_rotate_by_hena_regression_2` | `` | implemented MVP, smoke-covered; needs R oracle expansion | `` |
| `ena.rotate.by.mean` | `ena_rotate_by_mean` | `R/ena.rotate.by.mean.R` | mean rotation parity fixture coverage | `enaset, groups = NULL, params = groups` |
| `ena.rotation.h` | `ena_rotation_h` | `R/ena.rotation.h.R` | implemented MVP, smoke-covered; needs R oracle expansion | `enaset, params` |
| `ena.svd` | `ena_svd` | `R/ena.svd.R` | SVD parity fixture coverage | `enaset, params` |
| `ena.writeup` | `ena_writeup` | `R/ena.writeup.R` | not ported | `enaset, tool = "rENA", tool.version = as.character(packageVersion(tool)), comparison = NULL, comparison.groups = NULL, sig.dig = 2, output_dir = getwd(), type = c("file","stream"),` |
| `ena_correlation` | `ena_correlation` | `R/RcppExports.R` | implemented, smoke-covered | `points, centroids, conf_level = 0.95` |
| `find_binary_cols` | `find_binary_cols` | `R/utils.R` | not ported | `x, include_logical = FALSE` |
| `find_code_cols` | `find_code_cols` | `R/utils.R` | not ported | `x` |
| `find_dimension_cols` | `find_dimension_cols` | `R/utils.R` | not ported | `x` |
| `find_meta_cols` | `find_meta_cols` | `R/utils.R` | not ported | `x` |
| `fun_cohens.d` | `fun_cohens_d` | `R/cohens.d.R` | implemented, unit-tested | `x, y` |
| `fun_skip_sphere_norm` | `fun_skip_sphere_norm` | `R/RcppExports.R` | initial implementation | `dfM` |
| `fun_sphere_norm` | `fun_sphere_norm` | `R/RcppExports.R` | initial implementation | `dfM` |
| `get_x1_main_effect` | `get_x1_main_effect` | `R/gmr.R` | not ported | `V, X, alpha = 1, lambda = "lambda.min"` |
| `gmr` | `gmr` | `R/gmr.R` | implemented MVP, used by generalized rotation | `V,X` |
| `group` | `group` | `R/utils.plot.R` | not ported | `x, wh = NULL` |
| `horizon` | `horizon` | `R/qedata_define.R` | not ported | `x, ...` |
| `is.qe.code` | `is_qe_code` | `R/qedata_classes.R` | not ported | `x` |
| `is.qe.data` | `is_qe_data` | `R/qedata_classes.R` | not ported | `x` |
| `is.qe.horizon` | `is_qe_horizon` | `R/qedata_classes.R` | not ported | `x` |
| `is.qe.metadata` | `is_qe_metadata` | `R/qedata_classes.R` | not ported | `x` |
| `is.qe.unit` | `is_qe_unit` | `R/qedata_classes.R` | not ported | `x` |
| `means_rotate` | `means_rotate` | `R/utils.R` | not ported | `x, on = NULL` |
| `merge_columns_c` | `merge_columns_c` | `R/RcppExports.R` | not ported | `df, cols, sep = "::"` |
| `metadata` | `metadata` | `R/qedata_define.R` | not ported | `x, ...` |
| `methods_report` | `methods_report` | `R/ena.writeup.R` | not ported | `toc = FALSE, toc_depth = 3, fig_width = 5, fig_height = 4, keep_md = FALSE, md_extensions = NULL, pandoc_args = NULL` |
| `methods_report_stream` | `methods_report_stream` | `R/ena.writeup.R` | not ported | `toc = FALSE, toc_depth = 3, fig_width = 5, fig_height = 4, keep_md = FALSE, md_extensions = NULL, pandoc_args = NULL` |
| `model` | `model` | `R/piped.R` | initial implementation | `data, ..., normalize = sphere_norm, center_with = center, rotate_with = rotate, project_with = project, optimize_with = optimize, # Rotation specific parameters rotate_fun = ena.ro` |
| `move_nodes_to_unit_circle` | `move_nodes_to_unit_circle` | `R/move_nodes.R` | not ported | `set, dimension_name_1 = colnames(as.matrix(set$rotation$nodes))[1], dimension_name_2 = colnames(as.matrix(set$rotation$nodes))[2]` |
| `move_nodes_to_unit_circle_with_equal_space` | `move_nodes_to_unit_circle_with_equal_space` | `R/move_nodes.R` | not ported | `set, dimension_name_1 = colnames(as.matrix(set$rotation$nodes))[1], dimension_name_2 = colnames(as.matrix(set$rotation$nodes))[2]` |
| `namesToAdjacencyKey` | `names_to_adjacency_key` | `R/namesToAdjacencyKey.R` | initial implementation | `vector, upper_triangle = TRUE` |
| `optimize` | `optimize` | `R/piped.R` | not ported | `x, weights = NULL` |
| `project` | `project` | `R/piped.R` | initial implementation | `x, rotation = NULL, add.meta = TRUE` |
| `project_in` | `project_in` | `R/utils.R` | not ported | `x, by = NULL, ...` |
| `reclassify` | `reclassify` | `R/qedata_define.R` | not ported | `x, v, ...` |
| `remove_meta_data` | `remove_meta_data` | `R/utils.R` | not ported | `x` |
| `rotate` | `rotate` | `R/piped.R` | not ported | `x, ..., wh = ena.rotate.by.generalized` |
| `show` | `show` | `R/utils.plot.R` | not ported | `x, ...` |
| `sphere_norm` | `sphere_norm` | `R/piped.R` | initial implementation | `x, add.meta = TRUE` |
| `units` | `units` | `R/qedata_define.R` | not ported | `x, ...` |
| `vector_to_ut` | `vector_to_ut` | `R/RcppExports.R` | initial implementation | `v` |
| `with_means` | `with_means` | `R/utils.plot.R` | not ported | `x` |
| `with_trajectory` | `with_trajectory` | `R/utils.plot.R` | Plotly MVP, JSON smoke-covered | `x, ..., by = x$`_function.params`$conversation[1], add_jitter = TRUE, frame = 1100, transition = 1000, easing = "circle-in-out"` |

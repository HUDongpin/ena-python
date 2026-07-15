# Migration Guide

ena-python uses Python naming and objects while preserving rENA semantics where parity fixtures exist.

## Function Names

| rENA | ena-python |
|---|---|
| `ena(...)` | `ena(...)` |
| `ena.accumulate.data(...)` | `ena_accumulate_data(...)` or `accumulate_data(...)` |
| `ena.accumulate.data.file(...)` | `ena_accumulate_data_file(...)` |
| `ena.make.set(...)` | `ena_make_set(...)` or `make_set(...)` |
| `ena.svd(...)` | `ena_svd(...)` or `svd_rotation(...)` |
| `ena.rotate.by.mean(...)` | `ena_rotate_by_mean(...)` or `rotate_by_mean(...)` |
| `ena.rotate.by.generalized(...)` | `ena_rotate_by_generalized(...)` or `rotate_by_generalized(...)` |
| `ena.rotate.by.hena.regression(...)` | `ena_rotate_by_hena_regression(...)` or `rotate_by_regression(...)` |
| `ena.rotation.h(...)` | `ena_rotation_h(...)` or `rotation_h(...)` |
| `ena.plot(...)` | `ena_plot(...)` |

## Argument Names

| rENA argument | ena-python argument |
|---|---|
| `units.by` | `units` or `units_by` |
| `conversations.by` | `conversation` or `conversations_by` |
| `window.size.back` | `window_size_back` |
| `window.size.forward` | `window_size_forward` |
| `weight.by` | `weight_by` |
| `include.meta` | `include_meta` |
| `norm.by` | `norm_by` |
| `rotation.by` | `rotation_by` |
| `rotation.params` | `rotation_params` |
| `rotation.set` | `rotation_set` |
| `center.align.to.origin` | `center_align_to_origin` |

## Object Shape

Core ena-python objects are dataclasses with `to_dict()` methods:

- `ENAData`: raw rows, metadata, unit-level connection counts, row-level connection counts, trajectories, and function parameters.
- `ENASet`: line weights, centered projection inputs, points, node positions, centroids, variance, and rotation data.
- `ENARotationSet`: rotation matrix, codes, eigenvalues, nodes, and center vector.

Production code does not require R. R is used only to regenerate JSON oracle fixtures or to run tests marked `rcompat`.

## Current Compatibility Boundary

R oracle parity is strongest for accumulation fixtures, `make_set`, SVD rotation, mean rotation, rotation reuse, zero-network centering, and least-squares node positioning. Generalized/regression/hENA rotations are implemented as callable Python MVPs and smoke-tested, but still need expanded R oracle fixtures before they should be treated as exact replacements for all rENA edge cases.

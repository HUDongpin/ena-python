# Porting note 000: template start

This template includes initial Python implementations for a subset of rENA:

- `vector_to_ut`
- `svector_to_ut`/`adjacency_names`
- `rows_to_co_occurrences`
- `ref_window_df` equivalent
- `fun_sphere_norm` and max-norm scaling
- endpoint accumulation smoke path
- SVD projection path

The implementations are not yet certified as fully rENA-compatible. Use the R source and tests under `reference/rENA/` to drive parity work.

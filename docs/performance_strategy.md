# Performance strategy

ena-python exists because R-based ENA is difficult to scale for web workflows. Optimize in stages.

## Baseline

Start with correctness-oriented Pandas/NumPy. Capture benchmark numbers before optimizing.

The benchmark dataset is rENA's `RS.data`, which ships inside the rENA R package as an
`.rda` rather than as a CSV in this repo. Export it once:

```r
install.packages("rENA")          # see reference/README.md
library(rENA); data(RS.data)
write.csv(RS.data, "rs.data.csv", row.names = FALSE)
```

Then:

```bash
python scripts/benchmark_accumulation.py rs.data.csv \
  --units Condition UserName \
  --conversation ActivityNumber GroupName \
  --codes Data "Technical.Constraints" "Performance.Parameters" \
    "Client.and.Consultant.Requests" "Design.Reasoning" Collaboration
```

It times accumulation *and* modeling, taking `--repeats` samples (default 5) after
`--warmup` discarded runs (default 1), and reports the median with the observed range.

Baseline on `RS.data` (3824 rows, 48 units, 6 codes → 15 code pairs, `dimensions=2`),
median of 5 samples after 1 warmup:

| Stage | Before vectorizing | Now | |
|---|---:|---:|---:|
| `accumulate` | 0.0714 s | **0.0071 s** | 10.1x |
| `make_set` | 0.0017 s | 0.0016 s | — |
| **total** | **0.0731 s** | **0.0086 s** | **8.5x** |

Recorded on: Apple arm64, macOS 24.6, Python 3.14.6, numpy 2.5.1, pandas 3.0.3.
Numbers without that context are not comparable.

## What the vectorization actually bought

The plan below predicted the win would come from the moving-stanza window. Profiling
said otherwise, and it is worth recording why.

Vectorizing the window kernel (prefix sums instead of a per-row Python loop) made that
kernel **24–63x faster** in isolation — but only **1.26x** end-to-end. `cProfile` showed
the real cost was elsewhere:

| Component | Share of accumulation, before |
|---|---:|
| `_merge_columns` (building `a::b` unit keys) | **73%** |
| moving-stanza window | 23% |

`_merge_columns` used `.agg(sep.join, axis=1)`, a row-by-row pandas apply. `Series.str.cat`
does it in one pass. That single change was worth **2.8x** on its own — more than the
kernel the docs had pointed at.

The remaining cost was per-conversation DataFrame construction: `RS.data` has 87 short
conversations, and each paid for a fresh Index and block manager before being
`concat`-ed back together. Slicing the codes once into an ndarray and writing results at
their original row positions removed that, taking accumulation from 0.0204 s to 0.0071 s.

The lesson is the ordinary one: the hot path was not where the design doc assumed, and
one profile run settled it. Datasets with *few, long* conversations will see the kernel
speedup dominate instead; `RS.data` is the opposite shape.

## Regression guards

Wall-clock budgets do not survive a move to another machine, so the guards in
`tests/test_benchmarks.py` assert on how cost *grows* instead, fitting `t = c · n^k` and
checking the exponent. Calibrated by injecting real regressions:

| Variant | Fitted `k` |
|---|---:|
| As shipped | 1.01 – 1.03 |
| One numpy full-scan per row | 1.25 |
| A Python-loop scan per row (true O(n²)) | 1.97 |

The limit is `k < 1.5`: ~50% headroom over the real baseline, still failing on a genuine
quadratic. It is deliberately blind to constant-factor slowdowns — catching those needs a
stable machine and a committed baseline, which shared CI runners do not provide. Those
guards run in the normal suite; `make benchmark` runs the wall-clock measurements.

## Hot paths

Expected hot paths:

- moving stanza window co-occurrence generation
- grouping by conversation/unit
- trajectory accumulation
- large CSV loading and validation
- repeated web requests with similar schemas

## Acceleration plan

1. ~~Vectorize obvious Pandas loops.~~ **Done** — see above. `vector_to_ut` /
   `rows_to_co_occurrences` use precomputed upper-triangle index arrays,
   `ref_window_matrix` uses prefix sums, `_merge_columns` uses `str.cat`, and the
   per-conversation loop no longer builds a DataFrame per group.
2. ~~Cache adjacency pair indices.~~ **Done** — `_ut_indices` is `lru_cache`d and returns
   read-only arrays.
3. Add a Numba implementation of `ref_window_matrix` behind the same API. Lower priority
   now: the kernel is no longer the bottleneck at realistic conversation sizes, and Numba
   would not survive Pyodide.
4. Add Polars support for read/groupby-heavy workflows.
5. Consider sparse adjacency representations for many codes — the adjacency dimension
   still grows as P²/2.

## Web-service targets

A FastAPI request should be able to:

- validate columns quickly
- accumulate without copying unnecessary metadata
- return JSON-ready `ENASet.to_dict()` output
- support background-free synchronous requests for moderate datasets
- use async file upload only at the web layer, not in core algorithms

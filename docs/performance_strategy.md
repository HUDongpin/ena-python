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

| Stage | Median | Range |
|---|---:|---|
| `accumulate` | 0.0714 s | 0.0696 – 0.0896 s |
| `make_set` | 0.0017 s | 0.0015 – 0.0018 s |
| **total** | **0.0731 s** | |

Recorded on: Apple arm64, macOS 24.6, Python 3.14.6, numpy 2.5.1, pandas 3.0.3.
Numbers without that context are not comparable, which is why the earlier entry here
(one unwarmed sample, six decimal places, no hardware noted) is gone.

Accumulation dominates by ~40x, as expected: it is a Python-level loop over
rows × code pairs, while `make_set` works on the accumulated 48 × 15 matrix and barely
notices the row count.

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

1. Vectorize obvious Pandas loops.
2. Add a Numba implementation of `ref_window_matrix` behind the same API.
3. Add Polars support for read/groupby-heavy workflows.
4. Consider sparse adjacency representations for many codes.
5. Cache schema parsing and adjacency pair indices for web services.

## Web-service targets

A FastAPI request should be able to:

- validate columns quickly
- accumulate without copying unnecessary metadata
- return JSON-ready `ENASet.to_dict()` output
- support background-free synchronous requests for moderate datasets
- use async file upload only at the web layer, not in core algorithms

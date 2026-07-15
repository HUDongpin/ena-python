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
  --codes Data "Technical Constraints" "Performance Parameters" \
    "Client and Consultant Requests" "Design Reasoning" Collaboration
```

Baseline previously recorded on `RS.data`:

| Rows | Units | Elapsed seconds |
|---:|---:|---:|
| 3824 | 48 | 0.041557 |

Treat that number as indicative only: it carries no hardware or version details, and
`scripts/benchmark_accumulation.py` takes a single `perf_counter` sample with no warmup
or repetition. Re-measure on your own machine before drawing conclusions.

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

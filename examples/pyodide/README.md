# ena-python in the browser (Pyodide)

A working demonstration that ena-python runs as Python **in a browser tab** — no server,
no install, no R. It loads [Pyodide](https://pyodide.org/), installs ena-python from PyPI
with `micropip`, runs a real ENA pipeline, and plots the result.

The README claims browser support; this is the page that shows it.

## Run it

Any static file server works — the page is a single self-contained HTML file.

```bash
python3 -m http.server 8765 --directory examples/pyodide
# then open http://localhost:8765
```

Opening `index.html` directly from the filesystem will **not** work: Pyodide fetches its
WebAssembly runtime, and browsers block those requests on `file://`.

## Measured on a 2026 laptop (Chrome, warm CDN cache)

| Step | Elapsed |
|---|---:|
| Pyodide runtime ready | ~3 s |
| numpy + pandas + scipy loaded | ~9 s |
| `micropip.install("ena-python")` | ~0.7 s |
| **`ena()` on 4 units × 3 codes** | **~0.02 s** |
| Total, cold | ~18 s |

The analysis itself is milliseconds. Essentially all of the wait is downloading the
scientific stack as WebAssembly wheels — tens of megabytes, fetched once and then cached
by the browser. ena-python's own wheel is **147 KB**.

## Why this works at all

Three properties, each verifiable rather than aspirational:

1. **The wheel is pure Python** (`py3-none-any`, no compiled extensions), so `micropip`
   can install it directly from PyPI with no build step.
2. **The dependencies are numpy, pandas and scipy** — all three ship as Pyodide
   packages. Removing the unused `scikit-learn` dependency in 0.1.0 mattered here: it is
   heavy and would have been dead weight in the browser.
3. **The core touches nothing a browser forbids** — no subprocess, no filesystem, no
   sockets, no R. The R bridge exists only for generating test fixtures and is never
   imported by `ena_python`.

## What the demo shows

- **The ENA plot**: code nodes joined by edges whose width is the mean connection
  strength, with unit points on the same axes. Drawn as inline SVG so the page has no
  dependencies beyond Pyodide. ena-python ships Plotly helpers (`pip install
  "ena-python[plot]"`), but Plotly is an optional extra and not worth another megabyte
  here.
- **Unit positions and variance explained**, straight from the model object.

Node positions run roughly 6x wider than unit points, so four units cluster tightly near
the origin. That is what an ENA plot of four units looks like — `ena_plot` scales to the
network by default (`scale_to="network"`) — not a rendering bug.

## Verified

The page's output was checked against the same analysis run natively: unit coordinates
and variance match to four decimal places.

```
u1 -0.4571 +0.0529      SVD1  94.3%
u2 -0.0545 -0.1166      SVD2   4.6%
u3 +0.3855 +0.0378      SVD3   1.0%
u4 +0.1261 +0.0260
```

## Adapting it

Everything analytic lives in the `PYTHON` template string in `index.html`. Swap in your
own DataFrame and code columns; the API is identical to a local install, because it is
the same wheel.

To load your own CSV, fetch it and hand the text to pandas:

```js
const csv = await (await fetch("./my-data.csv")).text();
pyodide.globals.set("csv_text", csv);
pyodide.runPython(`
import io, pandas as pd
rows = pd.read_csv(io.StringIO(csv_text))
`);
```

## Notes

- Pinned to Pyodide **v314.0.2**, which ships numpy 2.4.3, pandas 3.0.2 and scipy 1.18.0
  — all satisfying ena-python's requirements.
- `micropip.install("ena-python")` takes whatever is current on PyPI. Pin it
  (`ena-python==0.1.0`) if you need a reproducible page.
- Loading only `numpy` and `pandas` is not enough: importing `ena_python` currently pulls
  `scipy` too, via `ena_python.stats`.

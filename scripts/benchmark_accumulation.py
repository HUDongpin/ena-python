from __future__ import annotations

import argparse
import time

from ena_python import accumulate
from ena_python.io import read_table


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    parser.add_argument("--units", nargs="+", required=True)
    parser.add_argument("--conversation", nargs="+", required=True)
    parser.add_argument("--codes", nargs="+", required=True)
    args = parser.parse_args()

    df = read_table(args.file)
    start = time.perf_counter()
    result = accumulate(df, units=args.units, conversation=args.conversation, codes=args.codes)
    elapsed = time.perf_counter() - start
    print(f"rows={len(df)} units={len(result.connection_counts)} elapsed_sec={elapsed:.6f}")


if __name__ == "__main__":
    main()

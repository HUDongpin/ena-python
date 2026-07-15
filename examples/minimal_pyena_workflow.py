from __future__ import annotations

import pandas as pd

from ena_python import ena


def main() -> None:
    rows = pd.DataFrame(
        {
            "UserName": ["u1", "u1", "u2", "u2"],
            "Condition": ["A", "A", "B", "B"],
            "GroupName": ["g1", "g1", "g2", "g2"],
            "Data": [1, 0, 1, 1],
            "Design": [0, 1, 1, 0],
            "Collaboration": [1, 1, 0, 1],
        }
    )
    result = ena(
        rows,
        codes=["Data", "Design", "Collaboration"],
        units=["Condition", "UserName"],
        conversation=["Condition", "GroupName"],
    )
    print(result.points)


if __name__ == "__main__":
    main()

from __future__ import annotations

import json

import pandas as pd
import pytest

from ena_python import accumulate, ena, ena_accumulate_data_file


def sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "UserName": ["u1", "u1", "u2", "u2"],
            "Condition": ["A", "A", "B", "B"],
            "GroupName": ["g1", "g1", "g2", "g2"],
            "Data": [1, 0, 1, 1],
            "Design": [0, 1, 1, 0],
            "Collaboration": [1, 1, 0, 1],
        }
    )


def test_accumulate_endpoint_smoke() -> None:
    got = accumulate(
        sample_df(),
        units=["Condition", "UserName"],
        conversation=["Condition", "GroupName"],
        codes=["Data", "Design", "Collaboration"],
    )
    assert got.connection_counts.shape == (2, 3)
    assert got.adjacency_names == [
        "Data & Design",
        "Data & Collaboration",
        "Design & Collaboration",
    ]


def test_ena_high_level_serializable() -> None:
    got = ena(
        sample_df(),
        units=["Condition", "UserName"],
        conversation=["Condition", "GroupName"],
        codes=["Data", "Design", "Collaboration"],
    )
    payload = got.to_dict()
    assert "points" in payload
    assert "rotation" in payload
    # Row-level detail is opt-in; the analytic results stand on their own.
    assert "row_connection_counts" not in payload["data"]
    assert "raw" not in payload["data"]
    json.dumps(payload)

    full = got.to_dict(include_raw=True)
    assert "row_connection_counts" in full["data"]
    assert "raw" in full["data"]
    json.dumps(full)


def test_conversation_window_counts_each_unit_conversation_once() -> None:
    df = pd.DataFrame(
        {
            "unit": ["u1", "u1", "u1"],
            "conversation": ["c1", "c1", "c2"],
            "A": [1, 0, 1],
            "B": [0, 1, 1],
        }
    )

    got = accumulate(
        df,
        units="unit",
        conversation="conversation",
        codes=["A", "B"],
        window="Conversation",
    )

    assert got.connection_counts["A & B"].tolist() == [2.0]


def test_ena_accumulate_data_accepts_separate_rena_frames() -> None:
    from ena_python.accumulation import ena_accumulate_data

    units = pd.DataFrame({"unit": ["u1", "u1", "u2"]})
    conversation = pd.DataFrame({"conversation": ["c1", "c1", "c1"]})
    codes = pd.DataFrame({"A": [1, 0, 1], "B": [0, 1, 1]})
    metadata = pd.DataFrame({"constant": ["x", "x", "y"], "varying": [1, 2, 3]})

    # A column that varies within a unit is dropped -- and that must be announced,
    # not silent, or the caller only discovers it when the column is missing later.
    with pytest.warns(UserWarning, match="varying"):
        got = ena_accumulate_data(
            units=units,
            conversation=conversation,
            codes=codes,
            metadata=metadata,
            window="Conversation",
        )

    assert got.units == ["unit"]
    assert got.conversation == ["conversation"]
    assert got.codes == ["A", "B"]
    assert got.connection_counts["A & B"].tolist() == [1.0, 1.0]
    assert "constant" in got.meta_data.columns
    assert "varying" not in got.meta_data.columns
    assert got.function_params["model"] == "EndPoint"


def test_stable_metadata_does_not_warn(recwarn) -> None:
    """Only *dropped* columns warn; a well-formed call must stay quiet."""

    from ena_python.accumulation import ena_accumulate_data

    df = pd.DataFrame(
        {
            "unit": ["u1", "u1", "u2", "u2"],
            "conversation": ["c1", "c1", "c1", "c1"],
            "constant": ["k1", "k1", "k2", "k2"],
            "A": [1, 0, 1, 1],
            "B": [0, 1, 1, 0],
        }
    )
    got = ena_accumulate_data(
        units=df[["unit"]],
        conversation=df[["conversation"]],
        codes=df[["A", "B"]],
        metadata=df[["constant"]],
    )
    assert "constant" in got.meta_data.columns
    assert not [w for w in recwarn.list if issubclass(w.category, UserWarning)]


def test_ena_accumulate_data_file_accepts_csv_path(tmp_path) -> None:
    csv_path = tmp_path / "toy.csv"
    sample_df().to_csv(csv_path, index=False)

    got = ena_accumulate_data_file(
        csv_path,
        units_by=["Condition", "UserName"],
        conversations_by=["Condition", "GroupName"],
        codes=["Data", "Design", "Collaboration"],
    )

    assert got.connection_counts.shape == (2, 3)
    assert got.row_connection_counts.shape[0] == len(sample_df())

    # The input dataset may hold personal data, so it is not echoed back by default.
    default_payload = got.to_dict()
    assert "raw" not in default_payload
    assert "row_connection_counts" not in default_payload
    assert default_payload["connection_counts"], "results must survive without raw"

    # ...but callers that want the echo can still opt in.
    full_payload = got.to_dict(include_raw=True)
    assert full_payload["raw"][0]["UserName"] == "u1"
    assert len(full_payload["row_connection_counts"]) == len(sample_df())

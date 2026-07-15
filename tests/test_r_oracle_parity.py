from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from pyena import accumulate, make_set
from pyena.rotation import rotate_by_mean

FIXTURE = Path("tests/fixtures/r_oracle/generated/rena_parity_model.json")


def _load_fixture() -> dict[str, Any]:
    if not FIXTURE.exists():
        pytest.skip("Generate R oracle fixtures with scripts/generate_r_oracle.py")
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _frame(records: list[dict[str, Any]], columns: list[str] | None = None) -> pd.DataFrame:
    df = pd.DataFrame.from_records(records)
    return df.loc[:, columns] if columns is not None else df


def _assert_frame_close(
    actual: pd.DataFrame, expected: pd.DataFrame, *, atol: float = 1e-8
) -> None:
    assert list(actual.columns) == list(expected.columns)
    assert len(actual) == len(expected)
    for column in expected.columns:
        if pd.api.types.is_numeric_dtype(expected[column]):
            np.testing.assert_allclose(
                actual[column].astype(float).to_numpy(),
                expected[column].astype(float).to_numpy(),
                atol=atol,
                rtol=0,
            )
        else:
            assert actual[column].astype(str).tolist() == expected[column].astype(str).tolist()


def _sign_align(actual: pd.DataFrame, expected: pd.DataFrame, dims: list[str]) -> pd.DataFrame:
    aligned = actual.copy()
    for dim in dims:
        dot = float((aligned[dim].astype(float) * expected[dim].astype(float)).sum())
        if dot < 0:
            aligned[dim] = -aligned[dim]
    return aligned


def _toy_accumulation(fixture: dict[str, Any]):
    return accumulate(
        pd.DataFrame(fixture["input"]),
        units=["unit"],
        conversation=["conv"],
        metadata=["group", "score"],
        codes=fixture["codes"],
        window_size_back=2,
    )


def test_accumulation_matches_r_oracle_fixture() -> None:
    fixture = _load_fixture()
    got = _toy_accumulation(fixture)
    expected = fixture["accumulate"]["endpoint"]

    edge_cols = ["A & B", "A & C", "B & C"]
    _assert_frame_close(
        got.connection_counts[edge_cols], _frame(expected["connection_counts"], edge_cols)
    )
    _assert_frame_close(
        got.meta_data[["ENA_UNIT", "unit", "group", "score"]],
        _frame(expected["meta_data"], ["ENA_UNIT", "unit", "group", "score"]),
    )


def test_make_set_svd_outputs_match_r_oracle_fixture() -> None:
    fixture = _load_fixture()
    got = make_set(_toy_accumulation(fixture), dimensions=2)
    expected = fixture["model"]
    edge_cols = ["A & B", "A & C", "B & C"]
    meta_cols = ["ENA_UNIT", "unit", "group", "score"]
    dims = ["SVD1", "SVD2"]

    _assert_frame_close(
        got.line_weights[meta_cols + edge_cols],
        _frame(expected["line_weights"], meta_cols + edge_cols),
    )
    _assert_frame_close(
        got.points_for_projection[meta_cols + edge_cols],
        _frame(expected["points_for_projection"], meta_cols + edge_cols),
    )

    expected_rotation = _frame(expected["rotation_matrix"], ["codes", *dims])
    actual_rotation = got.rotation.rotation.reset_index(names="codes")[["codes", *dims]]
    actual_rotation = _sign_align(actual_rotation, expected_rotation, dims)
    _assert_frame_close(actual_rotation, expected_rotation)

    expected_points = _frame(expected["points"], meta_cols + dims)
    actual_points = _sign_align(got.points[meta_cols + dims], expected_points, dims)
    _assert_frame_close(actual_points, expected_points)

    expected_nodes = _frame(expected["nodes"], ["code", *dims])
    actual_nodes = _sign_align(got.nodes[["code", *dims]], expected_nodes, dims)
    _assert_frame_close(actual_nodes, expected_nodes, atol=1e-7)

    expected_centroids = _frame(expected["centroids"], ["unit", *dims])
    actual_centroids = _sign_align(got.centroids[["unit", *dims]], expected_centroids, dims)
    _assert_frame_close(actual_centroids, expected_centroids, atol=1e-7)

    np.testing.assert_allclose(
        got.rotation.center_vec, np.asarray(expected["center_vec"]), atol=1e-10, rtol=0
    )
    # Compare variance across *every* dimension, not just the retained two. rENA
    # normalizes by the total over all dimensions (ena.make.set.R:332-335), and
    # slicing both sides to [:2] would hide a wrong denominator on this rank-2
    # toy. See test_rank3_* for the case that actually discriminates.
    np.testing.assert_allclose(
        got.variance.to_numpy(dtype=float),
        np.asarray(expected["variance"], dtype=float),
        atol=1e-10,
        rtol=0,
    )
    # rENA keeps eigenvalues for all dimensions as prcomp sdev^2 (ena.svd.R:57).
    np.testing.assert_allclose(
        np.asarray(got.rotation.eigenvalues, dtype=float),
        np.asarray(expected["eigenvalues"], dtype=float),
        atol=1e-10,
        rtol=0,
    )


def test_fixture_provenance_is_authoritative() -> None:
    """The golden fixture must come from real rENA, not the pure-R fallback.

    The fallback in scripts/generate_r_oracle.py re-implements ena.cpp the same way
    pyENA does, so a fixture built from it would only prove pyENA agrees with a
    re-implementation of itself.
    """

    provenance = _load_fixture().get("provenance")
    assert provenance is not None, "fixture carries no provenance; regenerate it"
    assert provenance["authoritative"] is True, (
        f"fixture came from non-authoritative oracle {provenance.get('oracle_mode')!r}"
    )
    assert provenance["rena_version"], "fixture does not record an rENA version"


def _rank3_accumulation(fixture: dict[str, Any]):
    rank3 = fixture["rank3"]
    return accumulate(
        pd.DataFrame(rank3["input"]),
        units=["unit"],
        conversation=["conv"],
        metadata=["grp"],
        codes=rank3["codes"],
        window_size_back=2,
    )


def test_rank3_variance_matches_r_oracle_over_all_dimensions() -> None:
    """Guards F-1: variance must be normalized by the total over ALL dimensions.

    The 3-unit toy has rank 2, so its 3rd singular value is ~0 and normalizing over
    2 dims vs all dims agree by accident. With 6 units x 4 codes the tail carries
    real variance (~13%), so a truncated denominator is off by several points.
    """

    fixture = _load_fixture()
    if "rank3" not in fixture:
        pytest.skip("Regenerate the fixture to include the rank3 case")
    got = make_set(_rank3_accumulation(fixture), dimensions=2)
    expected = np.asarray(fixture["rank3"]["model"]["variance"], dtype=float)

    assert len(expected) > 2, "rank3 fixture should span more than `dimensions` dims"
    assert expected[2:].sum() > 1e-3, "rank3 fixture must carry real variance beyond dim 2"

    np.testing.assert_allclose(got.variance.to_numpy(dtype=float), expected, atol=1e-10, rtol=0)


def test_rank3_eigenvalues_match_r_oracle() -> None:
    """Guards F-2: eigenvalues are prcomp sdev^2 == s^2/(n-1), for all dimensions."""

    fixture = _load_fixture()
    if "rank3" not in fixture:
        pytest.skip("Regenerate the fixture to include the rank3 case")
    got = make_set(_rank3_accumulation(fixture), dimensions=2)
    expected = np.asarray(fixture["rank3"]["model"]["eigenvalues"], dtype=float)

    actual = np.asarray(got.rotation.eigenvalues, dtype=float)
    assert actual.shape == expected.shape, (
        f"expected eigenvalues for all {len(expected)} dims, got {len(actual)}"
    )
    np.testing.assert_allclose(actual, expected, atol=1e-10, rtol=0)


def test_rotate_by_mean_matches_r_oracle_fixture() -> None:
    fixture = _load_fixture()
    accum = _toy_accumulation(fixture)
    got = make_set(
        accum,
        dimensions=2,
        rotation_by=rotate_by_mean,
        rotation_params=[accum.meta_data["group"] == "g1", accum.meta_data["group"] == "g2"],
    )
    expected = fixture["mean_model"]

    expected_rotation = _frame(expected["rotation_matrix"], ["codes", "MR1", "SVD2"])
    actual_rotation = got.rotation.rotation.reset_index(names="codes")[["codes", "MR1", "SVD2"]]
    actual_rotation = _sign_align(actual_rotation, expected_rotation, ["SVD2"])
    _assert_frame_close(actual_rotation, expected_rotation, atol=1e-7)


def test_rotation_set_reuse_matches_r_oracle_fixture() -> None:
    fixture = _load_fixture()
    base = make_set(_toy_accumulation(fixture), dimensions=2)
    reuse_accum = accumulate(
        pd.DataFrame(fixture["input"]),
        units=["group"],
        conversation=["conv"],
        metadata=["score"],
        codes=fixture["codes"],
        window_size_back=2,
    )
    got = make_set(reuse_accum, dimensions=2, rotation_set=base.rotation)
    expected = fixture["rotation_reuse"]
    dims = ["SVD1", "SVD2"]

    expected_points = _frame(expected["points"], ["ENA_UNIT", "group", *dims])
    actual_points = _sign_align(got.points[["ENA_UNIT", "group", *dims]], expected_points, dims)
    _assert_frame_close(actual_points, expected_points, atol=1e-7)

    expected_nodes = _frame(expected["nodes"], ["code", *dims])
    actual_nodes = _sign_align(got.nodes[["code", *dims]], expected_nodes, dims)
    _assert_frame_close(actual_nodes, expected_nodes, atol=1e-7)
    np.testing.assert_allclose(
        got.rotation.center_vec, np.asarray(expected["center_vec"]), atol=1e-10, rtol=0
    )


def test_zero_network_center_alignment_matches_r_oracle_behavior() -> None:
    fixture = _load_fixture()
    accum = _toy_accumulation(fixture)
    zero_units_value = fixture["zero_networks"]["zero_units"]
    zero_units = {zero_units_value} if isinstance(zero_units_value, str) else set(zero_units_value)
    zero_rows = accum.meta_data["ENA_UNIT"].isin(zero_units)
    accum.connection_counts.loc[zero_rows.to_numpy(), ["A & B", "A & C", "B & C"]] = 0

    centered = make_set(accum, dimensions=2, center_align_to_origin=True)
    uncentered = make_set(accum, dimensions=2, center_align_to_origin=False)

    np.testing.assert_allclose(
        centered.points.loc[zero_rows, ["SVD1", "SVD2"]].to_numpy(dtype=float),
        0,
        atol=1e-10,
    )
    assert not np.allclose(
        uncentered.points.loc[zero_rows, ["SVD1", "SVD2"]].to_numpy(dtype=float),
        0,
        atol=1e-10,
    )

# flake8: noqa: W191,E101
import sys
import typing
from builtins import range
from datetime import date, datetime, time
from io import BytesIO
from typing import Any, Iterator, Type
from unittest.mock import patch

import numpy as np
import pandas as pd
import pyarrow as pa
import pytest

import polars as pl
from polars import testing

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal  # pragma: no cover


def test_version() -> None:
    pl.__version__


def test_init_empty() -> None:
    # Empty initialization
    df1 = pl.DataFrame()
    assert df1.shape == (0, 0)


def test_init_only_columns() -> None:
    df = pl.DataFrame(columns=["a", "b", "c"])
    truth = pl.DataFrame({"a": [], "b": [], "c": []})
    assert df.shape == (0, 3)
    assert df.frame_equal(truth, null_equal=True)
    assert df.dtypes == [pl.Float32, pl.Float32, pl.Float32]

    # Validate construction with various flavours of no/empty data
    no_data: Any
    for no_data in (None, {}, []):
        df = pl.DataFrame(
            data=no_data,
            columns=[  # type: ignore
                ("a", pl.Date),
                ("b", pl.UInt64),
                ("c", pl.datatypes.Int8),
                ("d", pl.List(pl.UInt8)),
            ],
        )
        truth = pl.DataFrame({"a": [], "b": [], "c": []}).with_columns(
            [
                pl.col("a").cast(pl.Date),
                pl.col("b").cast(pl.UInt64),
                pl.col("c").cast(pl.Int8),
            ]
        )
        truth.insert_at_idx(3, pl.Series("d", [], pl.List(pl.UInt8)))

        assert df.shape == (0, 4)
        assert df.frame_equal(truth, null_equal=True)
        assert df.dtypes == [pl.Date, pl.UInt64, pl.Int8, pl.List]
        assert getattr(df.schema["d"], "inner") == pl.UInt8


def test_init_dict() -> None:
    # Empty dictionary
    df = pl.DataFrame({})
    assert df.shape == (0, 0)

    # Empty dictionary/values
    df = pl.DataFrame({"a": [], "b": []})
    assert df.shape == (0, 2)
    assert df.schema == {"a": pl.Float32, "b": pl.Float32}

    for df in (
        pl.DataFrame({}, columns={"a": pl.Date, "b": pl.Utf8}),
        pl.DataFrame({"a": [], "b": []}, columns={"a": pl.Date, "b": pl.Utf8}),
    ):
        assert df.shape == (0, 2)
        assert df.schema == {"a": pl.Date, "b": pl.Utf8}

    # List of empty list/tuple
    df = pl.DataFrame({"a": [[]], "b": [()]})
    assert df.schema == {"a": pl.List(pl.Float64), "b": pl.List(pl.Float64)}
    assert df.rows() == [([], [])]

    # Mixed dtypes
    df = pl.DataFrame({"a": [1, 2, 3], "b": [1.0, 2.0, 3.0]})
    assert df.shape == (3, 2)
    assert df.columns == ["a", "b"]
    assert df.dtypes == [pl.Int64, pl.Float64]

    df = pl.DataFrame(
        data={"a": [1, 2, 3], "b": [1.0, 2.0, 3.0]},
        columns=[("a", pl.Int8), ("b", pl.Float32)],
    )
    assert df.schema == {"a": pl.Int8, "b": pl.Float32}

    # Values contained in tuples
    df = pl.DataFrame({"a": (1, 2, 3), "b": [1.0, 2.0, 3.0]})
    assert df.shape == (3, 2)

    # Datetime/Date types (from both python and integer values)
    py_datetimes = (
        datetime(2022, 12, 31, 23, 59, 59),
        datetime(2022, 12, 31, 23, 59, 59),
    )
    py_dates = (date(2022, 12, 31), date(2022, 12, 31))
    int_datetimes = [1672531199000000, 1672531199000000]
    int_dates = [19357, 19357]

    for dates, datetimes, coldefs in (
        # test inferred and explicit (given both py/polars dtypes)
        (py_dates, py_datetimes, None),
        (py_dates, py_datetimes, [("dt", date), ("dtm", datetime)]),
        (py_dates, py_datetimes, [("dt", pl.Date), ("dtm", pl.Datetime)]),
        (int_dates, int_datetimes, [("dt", date), ("dtm", datetime)]),
        (int_dates, int_datetimes, [("dt", pl.Date), ("dtm", pl.Datetime)]),
    ):
        df = pl.DataFrame(
            data={"dt": dates, "dtm": datetimes},
            columns=coldefs,
        )
        assert df.schema == {"dt": pl.Date, "dtm": pl.Datetime}
        assert df.rows() == list(zip(py_dates, py_datetimes))

    # Overriding dict column names/types
    df = pl.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]}, columns=["c", "d"])
    assert df.columns == ["c", "d"]

    df = pl.DataFrame(
        {"a": [1, 2, 3], "b": [4, 5, 6]}, columns=["c", ("d", pl.Int8)]  # type: ignore[arg-type]
    )  # partial type info (allowed, but mypy doesn't like it ;p)
    assert df.schema == {"c": pl.Int64, "d": pl.Int8}

    df = pl.DataFrame(
        {"a": [1, 2, 3], "b": [4, 5, 6]}, columns=[("c", pl.Int8), ("d", pl.Int16)]
    )
    assert df.schema == {"c": pl.Int8, "d": pl.Int16}


def test_init_ndarray() -> None:
    # Empty array
    df = pl.DataFrame(np.array([]))
    assert df.frame_equal(pl.DataFrame())

    # 1D array
    df = pl.DataFrame(np.array([1, 2, 3]), columns=["a"])
    truth = pl.DataFrame({"a": [1, 2, 3]})
    assert df.frame_equal(truth)

    df = pl.DataFrame(np.array([1, 2, 3]), columns=[("a", pl.Int32)])
    truth = pl.DataFrame({"a": [1, 2, 3]}).with_column(pl.col("a").cast(pl.Int32))
    assert df.frame_equal(truth)

    # 2D array - default to column orientation
    df = pl.DataFrame(np.array([[1, 2], [3, 4]]), orient="column")
    truth = pl.DataFrame({"column_0": [1, 2], "column_1": [3, 4]})
    assert df.frame_equal(truth)

    df = pl.DataFrame([[1, 2.0, "a"], [None, None, None]], orient="row")
    truth = pl.DataFrame(
        {"column_0": [1, None], "column_1": [2.0, None], "column_2": ["a", None]}
    )
    assert df.frame_equal(truth)

    df = pl.DataFrame(
        data=[[1, 2.0, "a"], [None, None, None]],
        columns=[("x", pl.Boolean), ("y", pl.Int32), "z"],  # type: ignore[arg-type]
        orient="row",
    )
    assert df.rows() == [(True, 2, "a"), (None, None, None)]
    assert df.schema == {"x": pl.Boolean, "y": pl.Int32, "z": pl.Utf8}

    # TODO: Uncomment tests below when removing deprecation warning
    # # 2D array - default to column orientation
    # df = pl.DataFrame(np.array([[1, 2], [3, 4]]))
    # truth = pl.DataFrame({"column_0": [1, 2], "column_1": [3, 4]})
    # assert df.frame_equal(truth)

    # # 2D array - row orientation inferred
    # df = pl.DataFrame(np.array([[1, 2, 3], [4, 5, 6]]), columns=["a", "b", "c"])
    # truth = pl.DataFrame({"a": [1, 4], "b": [2, 5], "c": [3, 6]})
    # assert df.frame_equal(truth)

    # # 2D array - column orientation inferred
    # df = pl.DataFrame(np.array([[1, 2, 3], [4, 5, 6]]), columns=["a", "b"])
    # truth = pl.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    # assert df.frame_equal(truth)

    # 2D array - orientation conflicts with columns
    with pytest.raises(ValueError):
        pl.DataFrame(np.array([[1, 2, 3], [4, 5, 6]]), columns=["a", "b"], orient="row")
    with pytest.raises(ValueError):
        pl.DataFrame(
            np.array([[1, 2, 3], [4, 5, 6]]),
            columns=[("a", pl.UInt32), ("b", pl.UInt32)],
            orient="row",
        )

    # 3D array
    with pytest.raises(ValueError):
        _ = pl.DataFrame(np.random.randn(2, 2, 2))


# TODO: Remove this test case when removing deprecated behaviour
def test_init_ndarray_deprecated() -> None:
    with pytest.deprecated_call():
        # 2D array - default to row orientation
        df = pl.DataFrame(np.array([[1, 2], [3, 4]]))
        truth = pl.DataFrame({"column_0": [1, 3], "column_1": [2, 4]})
        assert df.frame_equal(truth)


def test_init_arrow() -> None:
    # Handle unnamed column
    df = pl.DataFrame(pa.table({"a": [1, 2], None: [3, 4]}))
    truth = pl.DataFrame({"a": [1, 2], "None": [3, 4]})
    assert df.frame_equal(truth)

    # Rename columns
    df = pl.DataFrame(pa.table({"a": [1, 2], "b": [3, 4]}), columns=["c", "d"])
    truth = pl.DataFrame({"c": [1, 2], "d": [3, 4]})
    assert df.frame_equal(truth)

    df = pl.DataFrame(
        pa.table({"a": [1, 2], None: [3, 4]}),
        columns=[("c", pl.Int32), ("d", pl.Float32)],
    )
    assert df.schema == {"c": pl.Int32, "d": pl.Float32}
    assert df.rows() == [(1, 3.0), (2, 4.0)]

    # Bad columns argument
    with pytest.raises(ValueError):
        pl.DataFrame(
            pa.table({"a": [1, 2, 3], "b": [4, 5, 6]}), columns=["c", "d", "e"]
        )


def test_init_series() -> None:
    # List of Series
    df = pl.DataFrame([pl.Series("a", [1, 2, 3]), pl.Series("b", [4, 5, 6])])
    truth = pl.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    assert df.frame_equal(truth)

    # Tuple of Series
    df = pl.DataFrame((pl.Series("a", (1, 2, 3)), pl.Series("b", (4, 5, 6))))
    assert df.frame_equal(truth)

    df = pl.DataFrame(
        (pl.Series("a", (1, 2, 3)), pl.Series("b", (4, 5, 6))),
        columns=[("x", pl.Float64), ("y", pl.Float64)],
    )
    assert df.schema == {"x": pl.Float64, "y": pl.Float64}
    assert df.rows() == [(1.0, 4.0), (2.0, 5.0), (3.0, 6.0)]

    # List of unnamed Series
    df = pl.DataFrame([pl.Series([1, 2, 3]), pl.Series([4, 5, 6])])
    truth = pl.DataFrame(
        [pl.Series("column_0", [1, 2, 3]), pl.Series("column_1", [4, 5, 6])]
    )
    assert df.frame_equal(truth)

    df = pl.DataFrame([pl.Series([0.0]), pl.Series([1.0])])
    assert df.schema == {"column_0": pl.Float64, "column_1": pl.Float64}
    assert df.rows() == [(0.0, 1.0)]

    df = pl.DataFrame(
        [pl.Series([None]), pl.Series([1.0])],
        columns=[("x", pl.Date), ("y", pl.Boolean)],
    )
    assert df.schema == {"x": pl.Date, "y": pl.Boolean}
    assert df.rows() == [(None, True)]

    # Single Series
    df = pl.DataFrame(pl.Series("a", [1, 2, 3]))
    truth = pl.DataFrame({"a": [1, 2, 3]})
    assert df.schema == {"a": pl.Int64}
    assert df.frame_equal(truth)

    df = pl.DataFrame(pl.Series("a", [1, 2, 3]), columns=[("a", pl.UInt32)])
    assert df.rows() == [(1,), (2,), (3,)]
    assert df.schema == {"a": pl.UInt32}


def test_init_seq_of_seq() -> None:
    # List of lists
    df = pl.DataFrame([[1, 2, 3], [4, 5, 6]], columns=["a", "b", "c"])
    truth = pl.DataFrame({"a": [1, 4], "b": [2, 5], "c": [3, 6]})
    assert df.frame_equal(truth)

    df = pl.DataFrame(
        [[1, 2, 3], [4, 5, 6]],
        columns=[("a", pl.Int8), ("b", pl.Int16), ("c", pl.Int32)],
    )
    assert df.schema == {"a": pl.Int8, "b": pl.Int16, "c": pl.Int32}
    assert df.rows() == [(1, 2, 3), (4, 5, 6)]

    # Tuple of tuples, default to column orientation
    df = pl.DataFrame(((1, 2, 3), (4, 5, 6)))
    truth = pl.DataFrame({"column_0": [1, 2, 3], "column_1": [4, 5, 6]})
    assert df.frame_equal(truth)

    # Row orientation
    df = pl.DataFrame(((1, 2), (3, 4)), columns=("a", "b"), orient="row")
    truth = pl.DataFrame({"a": [1, 3], "b": [2, 4]})
    assert df.frame_equal(truth)

    df = pl.DataFrame(
        ((1, 2), (3, 4)), columns=(("a", pl.Float32), ("b", pl.Float32)), orient="row"
    )
    assert df.schema == {"a": pl.Float32, "b": pl.Float32}
    assert df.rows() == [(1.0, 2.0), (3.0, 4.0)]


def test_init_1d_sequence() -> None:
    # Empty list
    df = pl.DataFrame([])
    assert df.frame_equal(pl.DataFrame())

    # List of strings
    df = pl.DataFrame(["a", "b", "c"], columns=["hi"])
    truth = pl.DataFrame({"hi": ["a", "b", "c"]})
    assert df.frame_equal(truth)

    df = pl.DataFrame([None, True, False], columns=[("xx", pl.Int8)])
    assert df.schema == {"xx": pl.Int8}
    assert df.rows() == [(None,), (1,), (0,)]

    # String sequence
    with pytest.raises(ValueError):
        pl.DataFrame("abc")


def test_init_pandas() -> None:
    pandas_df = pd.DataFrame([[1, 2], [3, 4]], columns=[1, 2])

    # pandas is available
    with patch("polars.internals.frame._PANDAS_AVAILABLE", True):
        # integer column names
        df = pl.DataFrame(pandas_df)
        truth = pl.DataFrame({"1": [1, 3], "2": [2, 4]})
        assert df.frame_equal(truth)
        assert df.schema == {"1": pl.Int64, "2": pl.Int64}

        # override column names, types
        df = pl.DataFrame(pandas_df, columns=[("x", pl.Float64), ("y", pl.Float64)])
        assert df.schema == {"x": pl.Float64, "y": pl.Float64}
        assert df.rows() == [(1.0, 2.0), (3.0, 4.0)]

    # pandas is not available
    with patch("polars.internals.frame._PANDAS_AVAILABLE", False):
        with pytest.raises(ValueError):
            pl.DataFrame(pandas_df)


def test_init_errors() -> None:
    # Length mismatch
    with pytest.raises(pl.ShapeError):
        pl.DataFrame({"a": [1, 2, 3], "b": [1.0, 2.0, 3.0, 4.0]})

    # Columns don't match data dimensions
    with pytest.raises(pl.ShapeError):
        pl.DataFrame([[1, 2], [3, 4]], columns=["a", "b", "c"])

    # Unmatched input
    with pytest.raises(ValueError):
        pl.DataFrame(0)


def test_init_records() -> None:
    dicts = [
        {"a": 1, "b": 2},
        {"b": 1, "a": 2},
        {"a": 1, "b": 2},
    ]
    df = pl.DataFrame(dicts)
    expected = pl.DataFrame({"a": [1, 2, 1], "b": [2, 1, 2]})
    assert df.frame_equal(expected)
    assert df.to_dicts() == dicts

    df_cd = pl.DataFrame(dicts, columns=["c", "d"])
    expected = pl.DataFrame({"c": [1, 2, 1], "d": [2, 1, 2]})
    assert df_cd.frame_equal(expected)

    df_xy = pl.DataFrame(dicts, columns=[("x", pl.UInt32), ("y", pl.UInt32)])
    expected = pl.DataFrame({"x": [1, 2, 1], "y": [2, 1, 2]}).with_columns(
        [pl.col("x").cast(pl.UInt32), pl.col("y").cast(pl.UInt32)]
    )
    assert df_xy.frame_equal(expected)
    assert df_xy.schema == {"x": pl.UInt32, "y": pl.UInt32}
    assert df_xy.rows() == [(1, 2), (2, 1), (1, 2)]


def test_selection() -> None:
    df = pl.DataFrame({"a": [1, 2, 3], "b": [1.0, 2.0, 3.0], "c": ["a", "b", "c"]})

    # get_column by name
    assert df.get_column("a").to_list() == [1, 2, 3]

    # select columns by mask
    assert df[:2, [True, False, False]].shape == (2, 1)
    assert df[:2, pl.Series([True, False, False])].shape == (2, 1)

    # column selection by string(s) in first dimension
    assert df["a"].to_list() == [1, 2, 3]
    assert df["b"].to_list() == [1.0, 2.0, 3.0]
    assert df["c"].to_list() == ["a", "b", "c"]

    # row selection by integers(s) in first dimension
    assert df[0].frame_equal(pl.DataFrame({"a": [1], "b": [1.0], "c": ["a"]}))
    assert df[-1].frame_equal(pl.DataFrame({"a": [3], "b": [3.0], "c": ["c"]}))

    # row, column selection when using two dimensions
    assert df[:, 0] == [1, 2, 3]
    assert df[:, 1] == [1.0, 2.0, 3.0]
    assert df[:2, 2] == ["a", "b"]

    assert df[[1, 2]].frame_equal(
        pl.DataFrame({"a": [2, 3], "b": [2.0, 3.0], "c": ["b", "c"]})
    )
    assert df[[-1, -2]].frame_equal(
        pl.DataFrame({"a": [3, 2], "b": [3.0, 2.0], "c": ["c", "b"]})
    )

    assert df[[True, False, True]].frame_equal(
        pl.DataFrame({"a": [1, 3], "b": [1.0, 3.0], "c": ["a", "c"]})
    )
    assert df[["a", "b"]].columns == ["a", "b"]
    assert df[[1, 2], [1, 2]].frame_equal(
        pl.DataFrame({"b": [2.0, 3.0], "c": ["b", "c"]})
    )
    assert df[1, 2] == "b"
    assert df[1, 1] == 2.0
    assert df[2, 0] == 3

    assert df[[True, False, True], "b"].shape == (2, 1)
    assert df[[True, False, False], ["a", "b"]].shape == (1, 2)

    assert df[[0, 1], "b"].shape == (2, 1)
    assert df[[2], ["a", "b"]].shape == (1, 2)
    assert df.select_at_idx(0).name == "a"
    assert (df["a"] == df["a"]).sum() == 3
    assert (df["c"] == df["a"].cast(str)).sum() == 0
    assert df[:, "a":"b"].shape == (3, 2)  # type: ignore
    assert df[:, "a":"c"].columns == ["a", "b", "c"]  # type: ignore
    expect = pl.DataFrame({"c": ["b"]})
    assert df[1, [2]].frame_equal(expect)
    expect = pl.DataFrame({"b": [1.0, 3.0]})
    assert df[[0, 2], [1]].frame_equal(expect)
    assert df[0, "c"] == "a"
    assert df[1, "c"] == "b"
    assert df[2, "c"] == "c"
    assert df[0, "a"] == 1

    # more slicing
    expect = pl.DataFrame({"a": [3, 2, 1], "b": [3.0, 2.0, 1.0], "c": ["c", "b", "a"]})
    assert df[::-1].frame_equal(expect)
    expect = pl.DataFrame({"a": [1, 2], "b": [1.0, 2.0], "c": ["a", "b"]})
    assert df[:-1].frame_equal(expect)

    expect = pl.DataFrame({"a": [1, 3], "b": [1.0, 3.0], "c": ["a", "c"]})
    assert df[::2].frame_equal(expect)


def test_from_arrow() -> None:
    tbl = pa.table(
        {
            "a": pa.array([1, 2], pa.timestamp("s")),
            "b": pa.array([1, 2], pa.timestamp("ms")),
            "c": pa.array([1, 2], pa.timestamp("us")),
            "d": pa.array([1, 2], pa.timestamp("ns")),
            "decimal1": pa.array([1, 2], pa.decimal128(2, 1)),
        }
    )
    assert pl.from_arrow(tbl).shape == (2, 5)


def test_sort() -> None:
    df = pl.DataFrame({"a": [2, 1, 3], "b": [1, 2, 3]})
    with pytest.deprecated_call():
        df.sort("a", in_place=True)
    assert df.frame_equal(pl.DataFrame({"a": [1, 2, 3], "b": [2, 1, 3]}))

    # test in-place + passing a list
    df = pl.DataFrame({"a": [2, 1, 3], "b": [1, 2, 3]})
    with pytest.deprecated_call():
        df.sort(["a", "b"], in_place=True)
    assert df.frame_equal(pl.DataFrame({"a": [1, 2, 3], "b": [2, 1, 3]}))


def test_replace() -> None:
    df = pl.DataFrame({"a": [2, 1, 3], "b": [1, 2, 3]})
    s = pl.Series("c", [True, False, True])
    df.replace("a", s)
    assert df.frame_equal(pl.DataFrame({"a": [True, False, True], "b": [1, 2, 3]}))


def test_assignment() -> None:
    df = pl.DataFrame({"foo": [1, 2, 3], "bar": [2, 3, 4]})
    df = df.with_column(pl.col("foo").alias("foo"))
    # make sure that assignment does not change column order
    assert df.columns == ["foo", "bar"]
    df = df.with_column(
        pl.when(pl.col("foo") > 1).then(9).otherwise(pl.col("foo")).alias("foo")
    )
    assert df["foo"].to_list() == [1, 9, 9]


def test_slice() -> None:
    df = pl.DataFrame({"a": [2, 1, 3], "b": ["a", "b", "c"]})
    df = df.slice(1, 2)
    assert df.frame_equal(pl.DataFrame({"a": [1, 3], "b": ["b", "c"]}))


def test_null_count() -> None:
    df = pl.DataFrame({"a": [2, 1, 3], "b": ["a", "b", None]})
    assert df.null_count().shape == (1, 2)


def test_head_tail_limit() -> None:
    df = pl.DataFrame({"a": range(10), "b": range(10)})
    assert df.head(5).height == 5
    assert df.limit(5).height == 5
    assert df.tail(5).height == 5

    assert not df.head(5).frame_equal(df.tail(5))
    # check if it doesn't fail when out of bounds
    assert df.head(100).height == 10
    assert df.limit(100).height == 10
    assert df.tail(100).height == 10

    # limit is an alias of head
    assert df.head(5).frame_equal(df.limit(5))


def test_drop_nulls() -> None:
    df = pl.DataFrame(
        {
            "foo": [1, 2, 3],
            "bar": [6, None, 8],
            "ham": ["a", "b", "c"],
        }
    )

    result = df.drop_nulls()
    expected = pl.DataFrame(
        {
            "foo": [1, 3],
            "bar": [6, 8],
            "ham": ["a", "c"],
        }
    )
    assert result.frame_equal(expected)

    # below we only drop entries if they are null in the column 'foo'
    result = df.drop_nulls("foo")
    assert result.frame_equal(df)


def test_pipe() -> None:
    df = pl.DataFrame({"foo": [1, 2, 3], "bar": [6, None, 8]})

    def _multiply(data: pl.DataFrame, mul: int) -> pl.DataFrame:
        return data * mul

    result = df.pipe(_multiply, mul=3)

    assert result.frame_equal(df * 3)


def test_explode() -> None:
    df = pl.DataFrame({"letters": ["c", "a"], "nrs": [[1, 2], [1, 3]]})
    out = df.explode("nrs")
    assert out["letters"].to_list() == ["c", "c", "a", "a"]
    assert out["nrs"].to_list() == [1, 2, 1, 3]


def test_groupby() -> None:
    df = pl.DataFrame(
        {
            "a": ["a", "b", "a", "b", "b", "c"],
            "b": [1, 2, 3, 4, 5, 6],
            "c": [6, 5, 4, 3, 2, 1],
        }
    )

    gb_df = df.groupby("a").agg({"b": ["sum", "min"], "c": "count"})
    assert "b_sum" in gb_df.columns
    assert "b_min" in gb_df.columns

    #
    # # TODO: is false because count is u32
    # df.groupby(by="a", select="b", agg="count").frame_equal(
    #     pl.DataFrame({"a": ["a", "b", "c"], "": [2, 3, 1]})
    # )
    assert df.groupby("a").apply(lambda df: df[["c"]].sum()).sort("c")["c"][0] == 1

    df_groups = df.groupby("a").groups().sort("a")
    assert df_groups["a"].series_equal(pl.Series("a", ["a", "b", "c"]))

    with pytest.deprecated_call():
        # TODO: find a way to avoid indexing into GroupBy
        for subdf in df.groupby("a"):  # type: ignore
            # TODO: add __next__() to GroupBy
            if subdf["a"][0] == "b":
                assert subdf.shape == (3, 3)

    assert df.groupby("a").get_group("c").shape == (1, 3)
    assert df.groupby("a").get_group("b").shape == (3, 3)
    assert df.groupby("a").get_group("a").shape == (2, 3)

    # Use lazy API in eager groupby
    assert df.groupby("a").agg([pl.sum("b")]).shape == (3, 2)
    # test if it accepts a single expression
    assert df.groupby("a").agg(pl.sum("b")).shape == (3, 2)

    df = pl.DataFrame(
        {
            "a": [1, 2, 3, 4, 5],
            "b": ["a", "a", "b", "b", "b"],
            "c": [None, 1, None, 1, None],
        }
    )

    # check if this query runs and thus column names propagate
    df.groupby("b").agg(pl.col("c").forward_fill()).explode("c")

    # get a specific column
    result = df.groupby("b").agg(pl.count("a"))
    assert result.shape == (2, 2)
    assert result.columns == ["b", "a"]

    # make sure all the methods below run
    assert df.groupby("b").first().shape == (2, 3)
    assert df.groupby("b").last().shape == (2, 3)
    assert df.groupby("b").max().shape == (2, 3)
    assert df.groupby("b").min().shape == (2, 3)
    assert df.groupby("b").count().shape == (2, 2)
    assert df.groupby("b").mean().shape == (2, 3)
    assert df.groupby("b").n_unique().shape == (2, 3)
    assert df.groupby("b").median().shape == (2, 3)
    # assert df.groupby("b").quantile(0.5).shape == (2, 3)
    assert df.groupby("b").agg_list().shape == (2, 3)


def test_pivot() -> None:
    df = pl.DataFrame(
        {
            "a": [1, 2, 3, 4, 5],
            "b": ["a", "a", "b", "b", "b"],
            "c": [None, 1, None, 1, None],
        }
    )
    gb = df.groupby("b").pivot("a", "c")
    assert gb.first().shape == (2, 6)
    assert gb.max().shape == (2, 6)
    assert gb.mean().shape == (2, 6)
    assert gb.count().shape == (2, 6)
    assert gb.median().shape == (2, 6)

    for agg_fn in ["sum", "min", "max", "mean", "count", "median", "mean"]:
        out = df.pivot(
            values="c", index="b", columns="a", aggregate_fn=agg_fn, sort_columns=True
        )
        assert out.shape == (2, 6)

    # example in polars-book
    df = pl.DataFrame(
        {
            "foo": ["A", "A", "B", "B", "C"],
            "N": [1, 2, 2, 4, 2],
            "bar": ["k", "l", "m", "n", "o"],
        }
    )
    out = df.groupby("foo").pivot(pivot_column="bar", values_column="N").first()
    assert out.shape == (3, 6)


def test_join() -> None:
    df_left = pl.DataFrame(
        {
            "a": ["a", "b", "a", "z"],
            "b": [1, 2, 3, 4],
            "c": [6, 5, 4, 3],
        }
    )
    df_right = pl.DataFrame(
        {
            "a": ["b", "c", "b", "a"],
            "k": [0, 3, 9, 6],
            "c": [1, 0, 2, 1],
        }
    )

    joined = df_left.join(df_right, left_on="a", right_on="a").sort("a")
    assert joined["b"].series_equal(pl.Series("b", [1, 3, 2, 2]))
    joined = df_left.join(df_right, left_on="a", right_on="a", how="left").sort("a")
    assert joined["c_right"].is_null().sum() == 1
    assert joined["b"].series_equal(pl.Series("b", [1, 3, 2, 2, 4]))
    joined = df_left.join(df_right, left_on="a", right_on="a", how="outer").sort("a")
    assert joined["c_right"].null_count() == 1
    assert joined["c"].null_count() == 1
    assert joined["b"].null_count() == 1
    assert joined["k"].null_count() == 1
    assert joined["a"].null_count() == 0

    # we need to pass in a column to join on, either by supplying `on`, or both `left_on` and `right_on`
    with pytest.raises(ValueError):
        df_left.join(df_right)
    with pytest.raises(ValueError):
        df_left.join(df_right, right_on="a")
    with pytest.raises(ValueError):
        df_left.join(df_right, left_on="a")

    df_a = pl.DataFrame({"a": [1, 2, 1, 1], "b": ["a", "b", "c", "c"]})
    df_b = pl.DataFrame(
        {"foo": [1, 1, 1], "bar": ["a", "c", "c"], "ham": ["let", "var", "const"]}
    )

    # just check if join on multiple columns runs
    df_a.join(df_b, left_on=["a", "b"], right_on=["foo", "bar"])

    eager_join = df_a.join(df_b, left_on="a", right_on="foo")

    lazy_join = df_a.lazy().join(df_b.lazy(), left_on="a", right_on="foo").collect()
    assert lazy_join.shape == eager_join.shape


def test_joins_dispatch() -> None:
    # this just flexes the dispatch a bit

    # don't change the data of this dataframe, this triggered:
    # https://github.com/pola-rs/polars/issues/1688
    dfa = pl.DataFrame(
        {
            "a": ["a", "b", "c", "a"],
            "b": [1, 2, 3, 1],
            "date": ["2021-01-01", "2021-01-02", "2021-01-03", "2021-01-01"],
            "datetime": [13241324, 12341256, 12341234, 13241324],
        }
    ).with_columns(
        [pl.col("date").str.strptime(pl.Date), pl.col("datetime").cast(pl.Datetime)]
    )

    for how in ["left", "inner", "outer"]:
        dfa.join(dfa, on=["a", "b", "date", "datetime"], how=how)
        dfa.join(dfa, on=["date", "datetime"], how=how)
        dfa.join(dfa, on=["date", "datetime", "a"], how=how)
        dfa.join(dfa, on=["date", "a"], how=how)
        dfa.join(dfa, on=["a", "datetime"], how=how)
        dfa.join(dfa, on=["date"], how=how)


@pytest.mark.parametrize(
    "stack,exp_shape,exp_columns",
    [
        ([pl.Series("stacked", [-1, -1, -1])], (3, 3), ["a", "b", "stacked"]),
        (
            [pl.Series("stacked2", [-1, -1, -1]), pl.Series("stacked3", [-1, -1, -1])],
            (3, 4),
            ["a", "b", "stacked2", "stacked3"],
        ),
    ],
)
@pytest.mark.parametrize("in_place", [True, False])
def test_hstack_list_of_series(
    stack: list, exp_shape: tuple, exp_columns: list, in_place: bool
) -> None:
    df = pl.DataFrame({"a": [2, 1, 3], "b": ["a", "b", "c"]})
    if in_place:
        df.hstack(stack, in_place=True)
        assert df.shape == exp_shape
        assert df.columns == exp_columns
    else:
        df_out = df.hstack(stack, in_place=False)
        assert df_out.shape == exp_shape
        assert df_out.columns == exp_columns


@pytest.mark.parametrize("in_place", [True, False])
def test_hstack_dataframe(in_place: bool) -> None:
    df = pl.DataFrame({"a": [2, 1, 3], "b": ["a", "b", "c"]})
    df2 = pl.DataFrame({"c": [2, 1, 3], "d": ["a", "b", "c"]})
    expected = pl.DataFrame(
        {"a": [2, 1, 3], "b": ["a", "b", "c"], "c": [2, 1, 3], "d": ["a", "b", "c"]}
    )
    if in_place:
        df.hstack(df2, in_place=True)
        assert df.frame_equal(expected)
    else:
        df_out = df.hstack(df2, in_place=False)
        assert df_out.frame_equal(expected)


@pytest.mark.parametrize("in_place", [True, False])
def test_vstack(in_place: bool) -> None:
    df1 = pl.DataFrame({"foo": [1, 2], "bar": [6, 7], "ham": ["a", "b"]})
    df2 = pl.DataFrame({"foo": [3, 4], "bar": [8, 9], "ham": ["c", "d"]})

    expected = pl.DataFrame(
        {"foo": [1, 2, 3, 4], "bar": [6, 7, 8, 9], "ham": ["a", "b", "c", "d"]}
    )

    out = df1.vstack(df2, in_place=in_place)
    if in_place:
        assert df1.frame_equal(expected)
    else:
        assert out.frame_equal(expected)  # type: ignore


def test_extend() -> None:
    with pl.StringCache():
        df1 = pl.DataFrame(
            {
                "foo": [1, 2],
                "bar": [True, False],
                "ham": ["a", "b"],
                "cat": ["A", "B"],
                "dates": [datetime(2021, 1, 1), datetime(2021, 2, 1)],
            }
        ).with_columns(
            [
                pl.col("cat").cast(pl.Categorical),
            ]
        )
        df2 = pl.DataFrame(
            {
                "foo": [3, 4],
                "bar": [True, None],
                "ham": ["c", "d"],
                "cat": ["C", "B"],
                "dates": [datetime(2022, 9, 1), datetime(2021, 2, 1)],
            }
        ).with_columns(
            [
                pl.col("cat").cast(pl.Categorical),
            ]
        )

    df1.extend(df2)
    expected = pl.DataFrame(
        {
            "foo": [1, 2, 3, 4],
            "bar": [True, False, True, None],
            "ham": ["a", "b", "c", "d"],
            "cat": ["A", "B", "C", "B"],
            "dates": [
                datetime(2021, 1, 1),
                datetime(2021, 2, 1),
                datetime(2022, 9, 1),
                datetime(2021, 2, 1),
            ],
        }
    ).with_column(
        pl.col("cat").cast(pl.Categorical),
    )
    assert df1.frame_equal(expected)


def test_drop() -> None:
    df = pl.DataFrame({"a": [2, 1, 3], "b": ["a", "b", "c"], "c": [1, 2, 3]})
    df = df.drop("a")
    assert df.shape == (3, 2)
    df = pl.DataFrame({"a": [2, 1, 3], "b": ["a", "b", "c"], "c": [1, 2, 3]})
    s = df.drop_in_place("a")
    assert s.name == "a"


def test_file_buffer() -> None:
    f = BytesIO()
    f.write(b"1,2,3,4,5,6\n7,8,9,10,11,12")
    f.seek(0)
    df = pl.read_csv(f, has_header=False)
    assert df.shape == (2, 6)

    f = BytesIO()
    f.write(b"1,2,3,4,5,6\n7,8,9,10,11,12")
    f.seek(0)
    # check if not fails on TryClone and Length impl in file.rs
    with pytest.raises(pl.ArrowError) as e:
        pl.read_parquet(f)
    assert "Invalid Parquet file" in str(e.value)


def test_read_missing_file() -> None:
    with pytest.raises(FileNotFoundError, match="fake_parquet_file"):
        pl.read_parquet("fake_parquet_file")

    with pytest.raises(FileNotFoundError, match="fake_csv_file"):
        pl.read_csv("fake_csv_file")

    with pytest.raises(FileNotFoundError, match="fake_csv_file"):
        with open("fake_csv_file", "r") as f:
            pl.read_csv(f)


def test_set() -> None:
    """Setting a dataframe using indices is deprecated. We keep these tests because we only generate a warning"""
    with pytest.deprecated_call():
        np.random.seed(1)
        df = pl.DataFrame(
            {"foo": np.random.rand(10), "bar": np.arange(10), "ham": ["h"] * 10}
        )
        df["new"] = np.random.rand(10)
        df[df["new"] > 0.5, "new"] = 1

        # set 2D
        df = pl.DataFrame({"b": [0, 0]})
        df[["A", "B"]] = [[1, 2], [1, 2]]
        assert df["A"] == [1, 1]
        assert df["B"] == [2, 2]

        with pytest.raises(ValueError):
            df[["C", "D"]] = 1
        with pytest.raises(ValueError):
            df[["C", "D"]] = [1, 1]
        with pytest.raises(ValueError):
            df[["C", "D"]] = [[1, 2, 3], [1, 2, 3]]

        # set tuple
        df = pl.DataFrame({"b": [0, 0]})
        df[0, "b"] = 1
        assert df[0, "b"] == 1

        df[0, 0] = 2
        assert df[0, "b"] == 2

        # row and col selection have to be int or str
        with pytest.raises(ValueError):
            df[:, [1]] = 1  # type: ignore
        with pytest.raises(ValueError):
            df[True, :] = 1  # type: ignore

        # needs to be a 2 element tuple
        with pytest.raises(ValueError):
            df[(1, 2, 3)] = 1  # type: ignore

        # we cannot index with any type, such as bool
        with pytest.raises(NotImplementedError):
            df[True] = 1  # type: ignore


def test_melt() -> None:
    df = pl.DataFrame({"A": ["a", "b", "c"], "B": [1, 3, 5], "C": [2, 4, 6]})
    melted = df.melt(id_vars="A", value_vars=["B", "C"])
    assert all(melted["value"] == [1, 3, 5, 2, 4, 6])

    melted = df.melt(id_vars="A", value_vars="B")
    assert all(melted["value"] == [1, 3, 5])
    n = 3
    for melted in [df.melt(), df.lazy().melt().collect()]:
        assert melted["variable"].to_list() == ["A"] * n + ["B"] * n + ["C"] * n
        assert melted["value"].to_list() == [
            "a",
            "b",
            "c",
            "1",
            "3",
            "5",
            "2",
            "4",
            "6",
        ]

    for melted in [
        df.melt(value_name="foo", variable_name="bar"),
        df.lazy().melt(value_name="foo", variable_name="bar").collect(),
    ]:
        assert melted["bar"].to_list() == ["A"] * n + ["B"] * n + ["C"] * n
        assert melted["foo"].to_list() == [
            "a",
            "b",
            "c",
            "1",
            "3",
            "5",
            "2",
            "4",
            "6",
        ]


def test_shift() -> None:
    df = pl.DataFrame({"A": ["a", "b", "c"], "B": [1, 3, 5]})
    a = df.shift(1)
    b = pl.DataFrame(
        {"A": [None, "a", "b"], "B": [None, 1, 3]},
    )
    assert a.frame_equal(b, null_equal=True)


def test_to_dummies() -> None:
    df = pl.DataFrame({"A": ["a", "b", "c"], "B": [1, 3, 5]})
    dummies = df.to_dummies()
    assert dummies["A_a"].to_list() == [1, 0, 0]
    assert dummies["A_b"].to_list() == [0, 1, 0]
    assert dummies["A_c"].to_list() == [0, 0, 1]


def test_custom_groupby() -> None:
    df = pl.DataFrame({"a": [1, 2, 1, 1], "b": ["a", "b", "c", "c"]})

    out = (
        df.lazy()
        .groupby("b")
        .agg([pl.col("a").apply(lambda x: x.sum(), return_dtype=pl.Int64)])
        .collect()
    )
    assert out.shape == (3, 2)


def test_multiple_columns_drop() -> None:
    df = pl.DataFrame({"a": [2, 1, 3], "b": [1, 2, 3], "c": [1, 2, 3]})
    out = df.drop(["a", "b"])
    assert out.columns == ["c"]


def test_concat() -> None:
    df = pl.DataFrame({"a": [2, 1, 3], "b": [1, 2, 3], "c": [1, 2, 3]})

    df2 = pl.concat([df, df])
    assert df2.shape == (6, 3)
    assert df2.n_chunks() == 1  # the default is to rechunk

    assert pl.concat([df, df], rechunk=False).n_chunks() == 2

    # check if a remains unchanged
    a = pl.from_records(((1, 2), (1, 2)))
    _ = pl.concat([a, a, a])
    assert a.shape == (2, 2)

    with pytest.raises(ValueError):
        _ = pl.concat([])

    with pytest.raises(ValueError):
        pl.concat([df, df], how="rubbish")


def test_arg_where() -> None:
    s = pl.Series([True, False, True, False])
    assert pl.arg_where(s).cast(int).series_equal(pl.Series([0, 2]))


def test_get_dummies() -> None:
    df = pl.DataFrame({"a": [1, 2, 3]})
    res = pl.get_dummies(df)
    expected = pl.DataFrame(
        {"a_1": [1, 0, 0], "a_2": [0, 1, 0], "a_3": [0, 0, 1]}
    ).with_columns(pl.all().cast(pl.UInt8))
    assert res.frame_equal(expected)


def test_to_pandas(df: pl.DataFrame) -> None:
    # pyarrow cannot deal with unsigned dictionary integer yet.
    # pyarrow cannot convert a time64 w/ non-zero nanoseconds
    df = df.drop(["cat", "time"])
    df.to_arrow()
    df.to_pandas()
    # test shifted df
    df.shift(2).to_pandas()
    df = pl.DataFrame({"col": pl.Series([True, False, True])})
    df.shift(2).to_pandas()


def test_from_arrow_table() -> None:
    data = {"a": [1, 2], "b": [1, 2]}
    tbl = pa.table(data)

    df: pl.DataFrame = pl.from_arrow(tbl)  # type: ignore
    df.frame_equal(pl.DataFrame(data))


def test_df_stats(df: pl.DataFrame) -> None:
    df.var()
    df.std()
    df.min()
    df.max()
    df.sum()
    df.mean()
    df.median()
    df.quantile(0.4, "nearest")


def test_df_fold() -> None:
    df = pl.DataFrame({"a": [2, 1, 3], "b": [1, 2, 3], "c": [1.0, 2.0, 3.0]})

    assert df.fold(lambda s1, s2: s1 + s2).series_equal(pl.Series("a", [4.0, 5.0, 9.0]))
    assert df.fold(lambda s1, s2: s1.zip_with(s1 < s2, s2)).series_equal(
        pl.Series("a", [1.0, 1.0, 3.0])
    )

    df = pl.DataFrame({"a": ["foo", "bar", "2"], "b": [1, 2, 3], "c": [1.0, 2.0, 3.0]})
    out = df.fold(lambda s1, s2: s1 + s2)
    out.series_equal(pl.Series("", ["foo11", "bar22", "233"]))

    df = pl.DataFrame({"a": [3, 2, 1], "b": [1, 2, 3], "c": [1.0, 2.0, 3.0]})
    # just check dispatch. values are tested on rust side.
    assert len(df.sum(axis=1)) == 3
    assert len(df.mean(axis=1)) == 3
    assert len(df.min(axis=1)) == 3
    assert len(df.max(axis=1)) == 3

    df_width_one = df[["a"]]
    assert df_width_one.fold(lambda s1, s2: s1).series_equal(df["a"])


def test_row_tuple() -> None:
    df = pl.DataFrame({"a": ["foo", "bar", "2"], "b": [1, 2, 3], "c": [1.0, 2.0, 3.0]})
    assert df.row(0) == ("foo", 1, 1.0)
    assert df.row(1) == ("bar", 2, 2.0)
    assert df.row(-1) == ("2", 3, 3.0)


def test_df_apply() -> None:
    df = pl.DataFrame({"a": ["foo", "bar", "2"], "b": [1, 2, 3], "c": [1.0, 2.0, 3.0]})
    out = df.apply(lambda x: len(x), None).to_series()
    assert out.sum() == 9


def test_column_names() -> None:
    tbl = pa.table(
        {
            "a": pa.array([1, 2, 3, 4, 5], pa.decimal128(38, 2)),
            "b": pa.array([1, 2, 3, 4, 5], pa.int64()),
        }
    )
    df: pl.DataFrame = pl.from_arrow(tbl)  # type: ignore
    assert df.columns == ["a", "b"]


def test_lazy_functions() -> None:
    df = pl.DataFrame({"a": ["foo", "bar", "2"], "b": [1, 2, 3], "c": [1.0, 2.0, 3.0]})
    out = df.select([pl.count("a")])
    assert out["a"] == 3
    assert pl.count(df["a"]) == 3
    out = df.select(
        [
            pl.var("b").alias("1"),
            pl.std("b").alias("2"),
            pl.max("b").alias("3"),
            pl.min("b").alias("4"),
            pl.sum("b").alias("5"),
            pl.mean("b").alias("6"),
            pl.median("b").alias("7"),
            pl.n_unique("b").alias("8"),
            pl.first("b").alias("9"),
            pl.last("b").alias("10"),
        ]
    )
    expected = 1.0
    assert np.isclose(out.select_at_idx(0), expected)
    assert np.isclose(pl.var(df["b"]), expected)  # type: ignore
    expected = 1.0
    assert np.isclose(out.select_at_idx(1), expected)
    assert np.isclose(pl.std(df["b"]), expected)  # type: ignore
    expected = 3
    assert np.isclose(out.select_at_idx(2), expected)
    assert np.isclose(pl.max(df["b"]), expected)
    expected = 1
    assert np.isclose(out.select_at_idx(3), expected)
    assert np.isclose(pl.min(df["b"]), expected)
    expected = 6
    assert np.isclose(out.select_at_idx(4), expected)
    assert np.isclose(pl.sum(df["b"]), expected)
    expected = 2
    assert np.isclose(out.select_at_idx(5), expected)
    assert np.isclose(pl.mean(df["b"]), expected)
    expected = 2
    assert np.isclose(out.select_at_idx(6), expected)
    assert np.isclose(pl.median(df["b"]), expected)
    expected = 3
    assert np.isclose(out.select_at_idx(7), expected)
    assert np.isclose(pl.n_unique(df["b"]), expected)
    expected = 1
    assert np.isclose(out.select_at_idx(8), expected)
    assert np.isclose(pl.first(df["b"]), expected)
    expected = 3
    assert np.isclose(out.select_at_idx(9), expected)
    assert np.isclose(pl.last(df["b"]), expected)
    expected = 3
    assert np.isclose(out.select_at_idx(9), expected)
    assert np.isclose(pl.last(df["b"]), expected)


def test_multiple_column_sort() -> None:
    df = pl.DataFrame({"a": ["foo", "bar", "2"], "b": [2, 2, 3], "c": [1.0, 2.0, 3.0]})
    out = df.sort([pl.col("b"), pl.col("c").reverse()])
    assert out["c"] == [2, 3, 1]
    assert out["b"] == [2, 2, 3]

    df = pl.DataFrame({"a": np.arange(1, 4), "b": ["a", "a", "b"]})

    df.sort("a", reverse=True).frame_equal(
        pl.DataFrame({"a": [3, 2, 1], "b": ["b", "a", "a"]})
    )

    df.sort("b", reverse=True).frame_equal(
        pl.DataFrame({"a": [3, 1, 2], "b": ["b", "a", "a"]})
    )

    df.sort(["b", "a"], reverse=[False, True]).frame_equal(
        pl.DataFrame({"a": [2, 1, 3], "b": ["a", "a", "b"]})
    )


def test_describe() -> None:
    df = pl.DataFrame(
        {
            "a": [1.0, 2.8, 3.0],
            "b": [4, 5, 6],
            "c": [True, False, True],
            "d": ["a", "b", "c"],
        }
    )
    assert df.describe().shape != df.shape
    assert set(df.describe().select_at_idx(2)) == {1.0, 4.0, 5.0, 6.0}


def test_string_cache_eager_lazy() -> None:
    # tests if the global string cache is really global and not interfered by the lazy execution.
    # first the global settings was thread-local and this breaks with the parallel execution of lazy
    with pl.StringCache():
        df1 = pl.DataFrame(
            {"region_ids": ["reg1", "reg2", "reg3", "reg4", "reg5"]}
        ).select([pl.col("region_ids").cast(pl.Categorical)])
        df2 = pl.DataFrame(
            {"seq_name": ["reg4", "reg2", "reg1"], "score": [3.0, 1.0, 2.0]}
        ).select([pl.col("seq_name").cast(pl.Categorical), pl.col("score")])

    expected = pl.DataFrame(
        {
            "region_ids": ["reg1", "reg2", "reg3", "reg4", "reg5"],
            "score": [2.0, 1.0, None, 3.0, None],
        }
    ).with_column(pl.col("region_ids").cast(pl.Categorical))

    assert df1.join(
        df2, left_on="region_ids", right_on="seq_name", how="left"
    ).frame_equal(expected, null_equal=True)


def test_assign() -> None:
    # check if can assign in case of a single column
    df = pl.DataFrame({"a": [1, 2, 3]})
    # test if we can assign in case of single column
    df = df.with_column(pl.col("a") * 2)
    assert df["a"] == [2, 4, 6]


def test_to_numpy() -> None:
    df = pl.DataFrame({"a": [1, 2, 3], "b": [1.0, 2.0, 3.0]})
    assert df.to_numpy().shape == (3, 2)


def test_argsort_by(df: pl.DataFrame) -> None:
    idx_df = df.select(pl.argsort_by(["int_nulls", "floats"], reverse=[False, True]))
    assert idx_df["int_nulls"] == [1, 0, 3]

    idx_df = df.select(pl.argsort_by(["int_nulls", "floats"], reverse=False))
    assert idx_df["int_nulls"] == [1, 0, 2]


def test_literal_series() -> None:
    df = pl.DataFrame(
        {
            "a": np.array([21.7, 21.8, 21], dtype=np.float32),
            "b": np.array([1, 3, 2], dtype=np.int64),
            "c": ["reg1", "reg2", "reg3"],
        }
    )
    out = (
        df.lazy()
        .with_column(pl.Series("e", [2, 1, 3]))  # type: ignore
        .with_column(pl.col("e").cast(pl.Float32))
        .collect()
    )
    assert out["e"] == [2, 1, 3]


def test_to_html(df: pl.DataFrame) -> None:
    # check if it does not panic/ error
    df._repr_html_()


def test_rows() -> None:
    df = pl.DataFrame({"a": [1, 2], "b": [1, 2]})
    assert df.rows() == [(1, 1), (2, 2)]


def test_rename(df: pl.DataFrame) -> None:
    out = df.rename({"strings": "bars", "int": "foos"})
    # check if wel can select these new columns
    _ = out[["foos", "bars"]]


def test_write_csv() -> None:
    df = pl.DataFrame(
        {
            "foo": [1, 2, 3, 4, 5],
            "bar": [6, 7, 8, 9, 10],
            "ham": ["a", "b", "c", "d", "e"],
        }
    )
    expected = "foo,bar,ham\n1,6,a\n2,7,b\n3,8,c\n4,9,d\n5,10,e\n"

    # if no file argument is supplied, write_csv() will return the string
    s = df.write_csv()
    assert s == expected

    # otherwise it will write to the file/iobuffer
    file = BytesIO()
    df.write_csv(file)
    file.seek(0)
    s = file.read().decode("utf8")
    assert s == expected


def test_from_rows() -> None:
    df = pl.from_records([[1, 2, "foo"], [2, 3, "bar"]], orient="row")
    assert df.frame_equal(
        pl.DataFrame(
            {"column_0": [1, 2], "column_1": [2, 3], "column_2": ["foo", "bar"]}
        )
    )

    df = pl.from_records(
        [[1, datetime.fromtimestamp(100)], [2, datetime.fromtimestamp(2398754908)]],
        orient="row",
    )
    assert df.dtypes == [pl.Int64, pl.Datetime]


def test_repeat_by() -> None:
    df = pl.DataFrame({"name": ["foo", "bar"], "n": [2, 3]})

    out = df.select(pl.col("n").repeat_by("n"))
    s = out["n"]
    assert s[0] == [2, 2]
    assert s[1] == [3, 3, 3]


def test_join_dates() -> None:
    date_times = pd.date_range(
        "2021-06-24 00:00:00", "2021-06-24 10:00:00", freq="1H", closed="left"
    )
    dts = (
        pl.from_pandas(date_times)
        .cast(int)
        .apply(lambda x: x + np.random.randint(1_000 * 60, 60_000 * 60))
        .cast(pl.Datetime)
    )

    # some df with sensor id, (randomish) datetime and some value
    df = pl.DataFrame(
        {
            "sensor": ["a"] * 5 + ["b"] * 5,
            "datetime": dts,
            "value": [2, 3, 4, 1, 2, 3, 5, 1, 2, 3],
        }
    )
    df.join(df, on="datetime")


def test_asof_cross_join() -> None:
    left = pl.DataFrame({"a": [-10, 5, 10], "left_val": ["a", "b", "c"]})
    right = pl.DataFrame({"a": [1, 2, 3, 6, 7], "right_val": [1, 2, 3, 6, 7]})

    # only test dispatch of asof join
    out = left.join_asof(right, on="a")
    assert out.shape == (3, 3)

    left.lazy().join_asof(right.lazy(), on="a").collect()
    assert out.shape == (3, 3)

    # only test dispatch of cross join
    out = left.join(right, how="cross")
    assert out.shape == (15, 4)

    left.lazy().join(right.lazy(), how="cross").collect()
    assert out.shape == (15, 4)


def test_str_concat() -> None:
    df = pl.DataFrame(
        {
            "nrs": [1, 2, 3, 4],
            "name": ["ham", "spam", "foo", None],
        }
    )
    out = df.with_column((pl.lit("Dr. ") + pl.col("name")).alias("graduated_name"))
    assert out["graduated_name"][0] == "Dr. ham"
    assert out["graduated_name"][1] == "Dr. spam"


def dot_product() -> None:
    df = pl.DataFrame({"a": [1, 2, 3, 4], "b": [2, 2, 2, 2]})

    assert df["a"].dot(df["b"]) == 20
    assert df.select([pl.col("a").dot("b")])[0, "a"] == 20


def test_hash_rows() -> None:
    df = pl.DataFrame({"a": [1, 2, 3, 4], "b": [2, 2, 2, 2]})
    assert df.hash_rows().dtype == pl.UInt64
    assert df["a"].hash().dtype == pl.UInt64
    assert df.select([pl.col("a").hash().alias("foo")])["foo"].dtype == pl.UInt64


def test_create_df_from_object() -> None:
    class Foo:
        def __init__(self, value: int) -> None:
            self._value = value

        def __eq__(self, other: Any) -> bool:
            return issubclass(other.__class__, self.__class__) and (
                self._value == other._value
            )

        def __repr__(self) -> str:
            return f"{self.__class__.__name__}({self._value})"

    # from miscellaneous object
    df = pl.DataFrame({"a": [Foo(1), Foo(2)]})
    assert df["a"].dtype == pl.Object
    assert df.rows() == [(Foo(1),), (Foo(2),)]

    # from mixed-type input
    df = pl.DataFrame({"x": [["abc", 12, 34.5]], "y": [1]})
    assert df.schema == {"x": pl.Object, "y": pl.Int64}
    assert df.rows() == [(["abc", 12, 34.5], 1)]


def test_hashing_on_python_objects() -> None:
    # see if we can do a groupby, drop_duplicates on a DataFrame with objects.
    # this requires that the hashing and aggregations are done on python objects

    df = pl.DataFrame({"a": [1, 1, 3, 4], "b": [1, 1, 2, 2]})

    class Foo:
        def __init__(self):  # type: ignore
            pass

        def __hash__(self):  # type: ignore
            return 0

        def __eq__(self, other):  # type: ignore
            return True

    df = df.with_column(pl.col("a").apply(lambda x: Foo()).alias("foo"))
    assert df.groupby(["foo"]).first().shape == (1, 3)
    assert df.distinct().shape == (3, 3)


def test_distinct_unit_rows() -> None:
    # simply test if we don't panic.
    pl.DataFrame({"a": [1], "b": [None]}).distinct(subset="a")


def test_panic() -> None:
    # may contain some tests that yielded a panic in polars or arrow
    # https://github.com/pola-rs/polars/issues/1110
    a = pl.DataFrame(
        {
            "col1": ["a"] * 500 + ["b"] * 500,
        }
    )
    a.filter(pl.col("col1") != "b")


def test_h_agg() -> None:
    df = pl.DataFrame({"a": [1, None, 3], "b": [1, 2, 3]})

    pl.testing.assert_series_equal(
        df.sum(axis=1, null_strategy="ignore"), pl.Series("a", [2, 2, 6])
    )
    pl.testing.assert_series_equal(
        df.sum(axis=1, null_strategy="propagate"), pl.Series("a", [2, None, 6])
    )
    pl.testing.assert_series_equal(
        df.mean(axis=1, null_strategy="propagate"), pl.Series("a", [1.0, None, 3.0])
    )


def test_slicing() -> None:
    # https://github.com/pola-rs/polars/issues/1322
    n = 20

    df = pl.DataFrame(
        {
            "d": ["u", "u", "d", "c", "c", "d", "d"] * n,
            "v1": [None, "help", None, None, None, None, None] * n,
        }
    )

    assert (df.filter(pl.col("d") != "d").select([pl.col("v1").unique()])).shape == (
        2,
        1,
    )


def test_apply_list_return() -> None:
    df = pl.DataFrame({"start": [1, 2], "end": [3, 5]})
    out = df.apply(lambda r: pl.Series(range(r[0], r[1] + 1))).to_series()
    assert out.to_list() == [[1, 2, 3], [2, 3, 4, 5]]


def test_apply_dataframe_return() -> None:
    df = pl.DataFrame({"a": [1, 2, 3], "b": ["c", "d", None]})

    out = df.apply(lambda row: (row[0] * 10, "foo", True, row[-1]))
    expected = pl.DataFrame(
        {
            "column_0": [10, 20, 30],
            "column_1": ["foo", "foo", "foo"],
            "column_2": [True, True, True],
            "column_3": ["c", "d", None],
        }
    )
    assert out.frame_equal(expected, null_equal=True)


def test_groupby_cat_list() -> None:  # noqa: W191,E101
    grouped = (
        pl.DataFrame(
            [
                pl.Series("str_column", ["a", "b", "b", "a", "b"]),
                pl.Series("int_column", [1, 1, 2, 2, 3]),
            ]
        )
        .with_column(pl.col("str_column").cast(pl.Categorical).alias("cat_column"))
        .groupby("int_column", maintain_order=True)
        .agg([pl.col("cat_column")])["cat_column"]
    )

    out = grouped.explode()
    assert out.dtype == pl.Categorical
    assert out[0] == "a"

    # test if we can also correctly fmt the categorical in list
    assert (
        str(grouped)
        == """shape: (3,)
Series: 'cat_column' [list]
[
	["a", "b"]
	["b", "a"]
	["b"]
]"""
    )


def test_groupby_agg_n_unique_floats() -> None:
    # tests proper dispatch
    df = pl.DataFrame({"a": [1, 1, 3], "b": [1.0, 2.0, 2.0]})

    for dtype in [pl.Float32, pl.Float64]:
        out = df.groupby("a", maintain_order=True).agg(
            [pl.col("b").cast(dtype).n_unique()]
        )
        assert out["b"].to_list() == [2, 1]


def test_select_by_dtype(df: pl.DataFrame) -> None:
    out = df.select(pl.col(pl.Utf8))
    assert out.columns == ["strings", "strings_nulls"]
    out = df.select(pl.col([pl.Utf8, pl.Boolean]))
    assert out.columns == ["strings", "strings_nulls", "bools", "bools_nulls"]


def test_with_row_count() -> None:
    df = pl.DataFrame({"a": [1, 1, 3], "b": [1.0, 2.0, 2.0]})

    out = df.with_row_count()
    assert out["row_nr"].to_list() == [0, 1, 2]

    out = df.lazy().with_row_count().collect()
    assert out["row_nr"].to_list() == [0, 1, 2]


def test_filter_with_all_expansion() -> None:
    df = pl.DataFrame(
        {
            "b": [1, 2, None],
            "c": [1, 2, None],
            "a": [None, None, None],
        }
    )
    out = df.filter(~pl.fold(True, lambda acc, s: acc & s.is_null(), pl.all()))
    assert out.shape == (2, 3)


def test_transpose() -> None:
    df = pl.DataFrame({"a": [1, 2, 3], "b": [1, 2, 3]})
    expected = pl.DataFrame(
        {
            "column": ["a", "b"],
            "column_0": [1, 1],
            "column_1": [2, 2],
            "column_2": [3, 3],
        }
    )
    out = df.transpose(include_header=True)
    assert expected.frame_equal(out)

    out = df.transpose(include_header=False, column_names=["a", "b", "c"])
    expected = pl.DataFrame(
        {
            "a": [1, 1],
            "b": [2, 2],
            "c": [3, 3],
        }
    )
    assert expected.frame_equal(out)

    out = df.transpose(
        include_header=True, header_name="foo", column_names=["a", "b", "c"]
    )
    expected = pl.DataFrame(
        {
            "foo": ["a", "b"],
            "a": [1, 1],
            "b": [2, 2],
            "c": [3, 3],
        }
    )
    assert expected.frame_equal(out)

    def name_generator() -> Iterator[str]:
        base_name = "my_column_"
        count = 0
        while True:
            yield f"{base_name}{count}"
            count += 1

    out = df.transpose(include_header=False, column_names=name_generator())
    expected = pl.DataFrame(
        {
            "my_column_0": [1, 1],
            "my_column_1": [2, 2],
            "my_column_2": [3, 3],
        }
    )
    assert expected.frame_equal(out)


def test_extension() -> None:
    class Foo:
        def __init__(self, value):  # type: ignore
            self.value = value

        def __repr__(self):  # type: ignore
            return f"foo({self.value})"

    foos = [Foo(1), Foo(2), Foo(3)]
    # I believe foos, stack, and sys.getrefcount have a ref
    base_count = 3
    assert sys.getrefcount(foos[0]) == base_count

    df = pl.DataFrame({"groups": [1, 1, 2], "a": foos})
    assert sys.getrefcount(foos[0]) == base_count + 1
    del df
    assert sys.getrefcount(foos[0]) == base_count

    df = pl.DataFrame({"groups": [1, 1, 2], "a": foos})
    assert sys.getrefcount(foos[0]) == base_count + 1

    out = df.groupby("groups", maintain_order=True).agg(pl.col("a").list().alias("a"))
    assert sys.getrefcount(foos[0]) == base_count + 2
    s = out["a"].explode()
    assert sys.getrefcount(foos[0]) == base_count + 3
    del s
    assert sys.getrefcount(foos[0]) == base_count + 2

    assert out["a"].explode().to_list() == foos
    assert sys.getrefcount(foos[0]) == base_count + 2
    del out
    assert sys.getrefcount(foos[0]) == base_count + 1
    del df
    assert sys.getrefcount(foos[0]) == base_count


def test_groupby_order_dispatch() -> None:
    df = pl.DataFrame({"x": list("bab"), "y": range(3)})
    expected = pl.DataFrame({"x": ["b", "a"], "count": [2, 1]})
    assert df.groupby("x", maintain_order=True).count().frame_equal(expected)
    expected = pl.DataFrame({"x": ["b", "a"], "y": [[0, 2], [1]]})
    assert df.groupby("x", maintain_order=True).agg_list().frame_equal(expected)


def test_partitioned_groupby_order() -> None:
    # check if group ordering is maintained.
    # we only have 30 groups, so this triggers a partitioned group by
    df = pl.DataFrame({"x": [chr(v) for v in range(33, 63)], "y": range(30)})
    out = df.groupby("x", maintain_order=True).agg(pl.all().list())
    assert out["x"] == df["x"]


def test_schema() -> None:
    df = pl.DataFrame(
        {"foo": [1, 2, 3], "bar": [6.0, 7.0, 8.0], "ham": ["a", "b", "c"]}
    )
    expected = {"foo": pl.Int64, "bar": pl.Float64, "ham": pl.Utf8}
    assert df.schema == expected


def test_df_schema_unique() -> None:
    df = pl.DataFrame({"a": [1, 2], "b": [3, 4]})
    with pytest.raises(Exception):
        df.columns = ["a", "a"]

    with pytest.raises(Exception):
        df.rename({"b": "a"})


def test_empty_projection() -> None:
    assert pl.DataFrame({"a": [1, 2], "b": [3, 4]}).select([]).shape == (0, 0)


def test_with_column_renamed() -> None:
    df = pl.DataFrame({"a": [1, 2], "b": [3, 4]})
    result = df.rename({"b": "c"})
    expected = pl.DataFrame({"a": [1, 2], "c": [3, 4]})
    assert result.frame_equal(expected)


def test_rename_swap() -> None:
    df = pl.DataFrame(
        {
            "a": [1, 2, 3, 4, 5],
            "b": [5, 4, 3, 2, 1],
        }
    )

    out = df.rename({"a": "b", "b": "a"})
    expected = pl.DataFrame(
        {
            "b": [1, 2, 3, 4, 5],
            "a": [5, 4, 3, 2, 1],
        }
    )
    assert out.frame_equal(expected)


def test_rename_same_name() -> None:
    df = pl.DataFrame(
        {
            "nrs": [1, 2, 3, 4, 5],
            "groups": ["A", "A", "B", "C", "B"],
        }
    ).lazy()
    df = df.rename({"groups": "groups"})
    df = df.select(["groups"])
    assert df.collect().to_dict(False) == {"groups": ["A", "A", "B", "C", "B"]}
    df = pl.DataFrame(
        {
            "nrs": [1, 2, 3, 4, 5],
            "groups": ["A", "A", "B", "C", "B"],
            "test": [1, 2, 3, 4, 5],
        }
    ).lazy()
    df = df.rename({"nrs": "nrs", "groups": "groups"})
    df = df.select(["groups"])
    df.collect()
    assert df.collect().to_dict(False) == {"groups": ["A", "A", "B", "C", "B"]}


def test_fill_null() -> None:
    df = pl.DataFrame({"a": [1, 2], "b": [3, None]})
    assert df.fill_null(4).frame_equal(pl.DataFrame({"a": [1, 2], "b": [3, 4]}))
    assert df.fill_null("max").frame_equal(pl.DataFrame({"a": [1, 2], "b": [3, 3]}))


def test_fill_nan() -> None:
    df = pl.DataFrame({"a": [1, 2], "b": [3.0, float("nan")]})
    assert df.fill_nan(4).frame_equal(pl.DataFrame({"a": [1, 2], "b": [3, 4]}))
    assert df["b"].fill_nan(5.0).to_list() == [3.0, 5.0]
    df = pl.DataFrame(
        {
            "a": [1.0, np.nan, 3.0],
            "b": [datetime(1, 2, 2), datetime(2, 2, 2), datetime(3, 2, 2)],
        }
    )
    assert df.fill_nan(2.0).dtypes == [pl.Float64, pl.Datetime]


def test_shift_and_fill() -> None:
    df = pl.DataFrame(
        {
            "foo": [1, 2, 3],
            "bar": [6, 7, 8],
            "ham": ["a", "b", "c"],
        }
    )
    result = df.shift_and_fill(periods=1, fill_value=0)
    expected = pl.DataFrame(
        {
            "foo": [0, 1, 2],
            "bar": [0, 6, 7],
            "ham": ["0", "a", "b"],
        }
    )
    assert result.frame_equal(expected)


def test_is_duplicated() -> None:
    df = pl.DataFrame({"foo": [1, 2, 2], "bar": [6, 7, 7]})
    assert df.is_duplicated().series_equal(pl.Series("", [False, True, True]))


def test_is_unique() -> None:
    df = pl.DataFrame({"foo": [1, 2, 2], "bar": [6, 7, 7]})
    assert df.is_unique().series_equal(pl.Series("", [True, False, False]))


def test_sample() -> None:
    df = pl.DataFrame({"foo": [1, 2, 3], "bar": [6, 7, 8], "ham": ["a", "b", "c"]})

    assert df.sample(n=2, seed=0).shape == (2, 3)
    assert df.sample(frac=0.4, seed=0).shape == (1, 3)


@pytest.mark.parametrize("in_place", [True, False])
def test_shrink_to_fit(in_place: bool) -> None:
    df = pl.DataFrame({"foo": [1, 2, 3], "bar": [6, 7, 8], "ham": ["a", "b", "c"]})

    if in_place:
        assert df.shrink_to_fit(typing.cast(Literal[True], in_place)) is None
    else:
        assert df.shrink_to_fit(typing.cast(Literal[False], in_place)).frame_equal(df)


def test_arithmetic() -> None:
    df = pl.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]})

    df_mul = df * 2
    expected = pl.DataFrame({"a": [2, 4], "b": [6, 8]})
    assert df_mul.frame_equal(expected)

    df_div = df / 2
    expected = pl.DataFrame({"a": [0.5, 1.0], "b": [1.5, 2.0]})
    assert df_div.frame_equal(expected)

    df_plus = df + 2
    expected = pl.DataFrame({"a": [3, 4], "b": [5, 6]})
    assert df_plus.frame_equal(expected)

    df_minus = df - 2
    expected = pl.DataFrame({"a": [-1, 0], "b": [1, 2]})
    assert df_minus.frame_equal(expected)

    df_mod = df % 2
    expected = pl.DataFrame({"a": [1.0, 0.0], "b": [1.0, 0.0]})
    assert df_mod.frame_equal(expected)

    df2 = pl.DataFrame({"c": [10]})

    out = df + df2
    expected = pl.DataFrame({"a": [11.0, None], "b": [None, None]}).with_column(
        pl.col("b").cast(pl.Float64)
    )
    assert out.frame_equal(expected, null_equal=True)

    out = df - df2
    expected = pl.DataFrame({"a": [-9.0, None], "b": [None, None]}).with_column(
        pl.col("b").cast(pl.Float64)
    )
    assert out.frame_equal(expected, null_equal=True)

    out = df / df2
    expected = pl.DataFrame({"a": [0.1, None], "b": [None, None]}).with_column(
        pl.col("b").cast(pl.Float64)
    )
    assert out.frame_equal(expected, null_equal=True)

    out = df * df2
    expected = pl.DataFrame({"a": [10.0, None], "b": [None, None]}).with_column(
        pl.col("b").cast(pl.Float64)
    )
    assert out.frame_equal(expected, null_equal=True)

    out = df % df2
    expected = pl.DataFrame({"a": [1.0, None], "b": [None, None]}).with_column(
        pl.col("b").cast(pl.Float64)
    )
    assert out.frame_equal(expected, null_equal=True)

    # cannot do arithmetic with a sequence
    with pytest.raises(ValueError, match="Operation not supported"):
        _ = df + [1]  # type: ignore


def test_add_string() -> None:
    df = pl.DataFrame({"a": ["hi", "there"], "b": ["hello", "world"]})
    result = df + " hello"
    expected = pl.DataFrame(
        {"a": ["hi hello", "there hello"], "b": ["hello hello", "world hello"]}
    )
    assert result.frame_equal(expected)


def test_getattr() -> None:
    with pytest.deprecated_call():
        df = pl.DataFrame({"a": [1.0, 2.0]})
        testing.assert_series_equal(df.a, pl.Series("a", [1.0, 2.0]))

        with pytest.raises(AttributeError):
            _ = df.b


def test_get_item() -> None:
    """test all the methods to use [] on a dataframe"""
    df = pl.DataFrame({"a": [1.0, 2.0], "b": [3, 4]})

    # expression
    assert df.select(pl.col("a")).frame_equal(pl.DataFrame({"a": [1.0, 2.0]}))

    # numpy array
    assert df[np.array([True, False])].frame_equal(pl.DataFrame({"a": [1.0], "b": [3]}))

    # tuple. The first element refers to the rows, the second element to columns
    assert df[:, :].frame_equal(df)

    # str, always refers to a column name
    assert df["a"].series_equal(pl.Series("a", [1.0, 2.0]))

    # int, always refers to a row index (zero-based): index=1 => second row
    assert df[1].frame_equal(pl.DataFrame({"a": [2.0], "b": [4]}))

    # range, refers to rows
    assert df[range(1)].frame_equal(pl.DataFrame({"a": [1.0], "b": [3]}))

    # slice. Below an example of taking every second row
    assert df[::2].frame_equal(pl.DataFrame({"a": [1.0], "b": [3]}))

    # numpy array; assumed to be row indices if integers, or columns if strings
    # TODO: add boolean mask support
    df[np.array([1])].frame_equal(pl.DataFrame({"a": [2.0], "b": [4]}))
    df[np.array(["a"])].frame_equal(pl.DataFrame({"a": [1.0, 2.0]}))
    # note that we cannot use floats (even if they could be casted to integer without loss)
    with pytest.raises(NotImplementedError):
        _ = df[np.array([1.0])]

    # sequences (lists or tuples; tuple only if length != 2)
    # if strings or list of expressions, assumed to be column names
    # if bools, assumed to be a row mask
    # if integers, assumed to be row indices
    assert df[["a", "b"]].frame_equal(df)
    assert df.select([pl.col("a"), pl.col("b")]).frame_equal(df)
    df[[1]].frame_equal(pl.DataFrame({"a": [1.0], "b": [3]}))
    df[[False, True]].frame_equal(pl.DataFrame({"a": [1.0], "b": [3]}))

    # pl.Series: like sequences, but only for rows
    df[[1]].frame_equal(pl.DataFrame({"a": [1.0], "b": [3]}))
    df[[False, True]].frame_equal(pl.DataFrame({"a": [1.0], "b": [3]}))
    with pytest.raises(NotImplementedError):
        _ = df[pl.Series("", ["hello Im a string"])]


def test_pivot_list() -> None:
    df = pl.DataFrame({"a": [1, 2, 3], "b": [[1, 1], [2, 2], [3, 3]]})

    expected = pl.DataFrame(
        {
            "a": [1, 2, 3],
            "1": [[1, 1], None, None],
            "2": [None, [2, 2], None],
            "3": [None, None, [3, 3]],
        }
    )

    out = df.pivot("b", index="a", columns="a", aggregate_fn="first", sort_columns=True)

    assert out.frame_equal(expected, null_equal=True)


@pytest.mark.parametrize("as_series,inner_dtype", [(True, pl.Series), (False, list)])
def test_to_dict(as_series: bool, inner_dtype: Any) -> None:
    df = pl.DataFrame(
        {
            "A": [1, 2, 3, 4, 5],
            "fruits": ["banana", "banana", "apple", "apple", "banana"],
            "B": [5, 4, 3, 2, 1],
            "cars": ["beetle", "audi", "beetle", "beetle", "beetle"],
            "optional": [28, 300, None, 2, -30],
        }
    )

    s = df.to_dict(as_series=as_series)
    assert isinstance(s, dict)
    for v in s.values():
        assert isinstance(v, inner_dtype)
        assert len(v) == len(df)


def test_df_broadcast() -> None:
    df = pl.DataFrame({"a": [1, 2, 3]})
    out = df.with_column(pl.Series([[1, 2]]))
    assert out.shape == (3, 2)


def test_product() -> None:
    df = pl.DataFrame(
        {
            "int": [1, 2, 3],
            "flt": [-1.0, 12.0, 9.0],
            "bool_0": [True, False, True],
            "bool_1": [True, True, True],
        }
    )
    out = df.product()
    expected = pl.DataFrame({"int": [6], "flt": [-108.0], "bool_0": [0], "bool_1": [1]})
    assert out.frame_equal(expected)


def test_first_last_expression(fruits_cars: pl.DataFrame) -> None:
    df = fruits_cars
    out = df.select(pl.first())
    assert out.columns == ["A"]

    out = df.select(pl.last())
    assert out.columns == ["cars"]


def test_empty_is_in() -> None:
    assert pl.DataFrame({"foo": ["a", "b", "c", "d"]}).filter(
        pl.col("foo").is_in([])
    ).shape == (0, 1)


def test_groupby_slice_expression_args() -> None:
    df = pl.DataFrame({"groups": ["a"] * 10 + ["b"] * 20, "vals": range(30)})

    out = (
        df.groupby("groups", maintain_order=True)
        .agg([pl.col("vals").slice(pl.count() * 0.1, (pl.count() // 5))])
        .explode("vals")
    )

    expected = pl.DataFrame(
        {"groups": ["a", "a", "b", "b", "b", "b"], "vals": [1, 2, 12, 13, 14, 15]}
    )
    assert out.frame_equal(expected)


def test_join_suffixes() -> None:
    df_a = pl.DataFrame({"A": [1], "B": [1]})
    df_b = pl.DataFrame({"A": [1], "B": [1]})

    for how in ["left", "inner", "outer", "cross"]:
        # no need for an essert, we error if wrong
        df_a.join(df_b, on="A", suffix="_y", how=how)["B_y"]

    df_a.join_asof(df_b, on="A", suffix="_y")["B_y"]


def test_preservation_of_subclasses() -> None:
    """Tests for DataFrame inheritance."""

    # We should be able to inherit from polars.DataFrame
    class SubClassedDataFrame(pl.DataFrame):
        pass

    # The constructor creates an object which is an instance of both the
    # superclass and subclass
    df = SubClassedDataFrame({"column_1": [1, 2, 3]})
    assert isinstance(df, pl.DataFrame)
    assert isinstance(df, SubClassedDataFrame)

    # Methods which yield new dataframes should preserve the subclass,
    # and here we choose a random method to test with
    assert isinstance(df.transpose(), SubClassedDataFrame)

    # The type of the dataframe should be preserved when casted to LazyFrame and back
    assert isinstance(df.lazy().collect(), SubClassedDataFrame)

    # Check if the end user can extend the functionality of both DataFrame and LazyFrame
    # and connect these classes together
    class MyLazyFrame(pl.LazyFrame):
        @property
        def _dataframe_class(cls) -> "Type[MyDataFrame]":
            return MyDataFrame

    class MyDataFrame(pl.DataFrame):
        _lazyframe_class = MyLazyFrame

    assert isinstance(MyDataFrame().lazy(), MyLazyFrame)
    assert isinstance(MyDataFrame().lazy().collect(), MyDataFrame)


def test_preservation_of_subclasses_after_groupby_statements() -> None:
    """Group by operations should preserve inherited dataframe classes."""

    class SubClassedDataFrame(pl.DataFrame):
        pass

    # A group by operation should preserve the subclass
    subclassed_df = SubClassedDataFrame({"a": [1, 2], "b": [3, 4]})
    groupby = subclassed_df.groupby("a")
    assert isinstance(groupby.agg(pl.count()), SubClassedDataFrame)

    # Round-trips to GBSelection and back should also preserve subclass
    assert isinstance(
        groupby.agg(pl.col("a").count().alias("count")), SubClassedDataFrame
    )

    # Round-trips to PivotOps and back should also preserve subclass
    assert isinstance(
        groupby.pivot(pivot_column="a", values_column="b").first(),
        SubClassedDataFrame,
    )


def test_explode_empty() -> None:
    df = (
        pl.DataFrame(dict(x=["a", "a", "b", "b"], y=[1, 1, 2, 2]))
        .groupby("x")
        .agg(pl.col("y").take([]))
    )
    assert df.explode("y").shape == (0, 2)

    df = pl.DataFrame(dict(x=["1", "2", "4"], y=[["a", "b", "c"], ["d"], []]))
    assert df.explode("y").frame_equal(
        pl.DataFrame({"x": ["1", "1", "1", "2", "4"], "y": ["a", "b", "c", "d", None]})
    )


def test_asof_by_multiple_keys() -> None:
    lhs = pl.DataFrame(
        {
            "a": [-20, -19, 8, 12, 14],
            "by": [1, 1, 2, 2, 2],
            "by2": [1, 1, 2, 2, 2],
        }
    )

    rhs = pl.DataFrame(
        {
            "a": [-19, -15, 3, 5, 13],
            "by": [1, 1, 2, 2, 2],
            "by2": [1, 1, 2, 2, 2],
        }
    )

    assert (
        lhs.join_asof(rhs, on="a", by=["by", "by2"], strategy="backward")
        .select(["a", "by"])
        .frame_equal(pl.DataFrame({"a": [-20, -19, 8, 12, 14], "by": [1, 1, 2, 2, 2]}))
    )


@typing.no_type_check
def test_partition_by() -> None:
    df = pl.DataFrame(
        {
            "foo": ["A", "A", "B", "B", "C"],
            "N": [1, 2, 2, 4, 2],
            "bar": ["k", "l", "m", "m", "l"],
        }
    )

    assert [
        a.to_dict(False) for a in df.partition_by(["foo", "bar"], maintain_order=True)
    ] == [
        {"foo": ["A"], "N": [1], "bar": ["k"]},
        {"foo": ["A"], "N": [2], "bar": ["l"]},
        {"foo": ["B", "B"], "N": [2, 4], "bar": ["m", "m"]},
        {"foo": ["C"], "N": [2], "bar": ["l"]},
    ]

    assert [a.to_dict(False) for a in df.partition_by("foo", maintain_order=True)] == [
        {"foo": ["A", "A"], "N": [1, 2], "bar": ["k", "l"]},
        {"foo": ["B", "B"], "N": [2, 4], "bar": ["m", "m"]},
        {"foo": ["C"], "N": [2], "bar": ["l"]},
    ]

    df = pl.DataFrame({"a": ["one", "two", "one", "two"], "b": [1, 2, 3, 4]})
    assert df.partition_by(["a", "b"], as_dict=True)["one", 1].to_dict(False) == {
        "a": ["one"],
        "b": [1],
    }
    assert df.partition_by(["a"], as_dict=True)["one"].to_dict(False) == {
        "a": ["one", "one"],
        "b": [1, 3],
    }


@typing.no_type_check
def test_list_of_list_of_struct() -> None:
    expected = [{"list_of_list_of_struct": [[{"a": 1}, {"a": 2}]]}]
    pa_df = pa.Table.from_pylist(expected)
    df = pl.from_arrow(pa_df)
    assert df.rows() == [([[{"a": 1}, {"a": 2}]],)]
    assert df.to_dicts() == expected


def test_concat_to_empty() -> None:
    assert pl.concat([pl.DataFrame([]), pl.DataFrame({"a": [1]})]).to_dict(False) == {
        "a": [1]
    }


def test_fill_null_limits() -> None:
    assert pl.DataFrame(
        {
            "a": [1, None, None, None, 5, 6, None, None, None, 10],
            "b": ["a", None, None, None, "b", "c", None, None, None, "d"],
            "c": [True, None, None, None, False, True, None, None, None, False],
        }
    ).select(
        [
            pl.all().fill_null("forward", limit=2),
            pl.all().fill_null("backward", limit=2).suffix("_backward"),
        ]
    ).to_dict(
        False
    ) == {
        "a": [1, 1, 1, None, 5, 6, 6, 6, None, 10],
        "b": ["a", "a", "a", None, "b", "c", "c", "c", None, "d"],
        "c": [True, True, True, None, False, True, True, True, None, False],
        "a_backward": [1, None, 5, 5, 5, 6, None, 10, 10, 10],
        "b_backward": ["a", None, "b", "b", "b", "c", None, "d", "d", "d"],
        "c_backward": [
            True,
            None,
            False,
            False,
            False,
            True,
            None,
            False,
            False,
            False,
        ],
    }

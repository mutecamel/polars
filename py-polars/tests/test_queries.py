from datetime import datetime

import numpy as np

import polars as pl


def test_sort_by_bools() -> None:
    # tests dispatch
    df = pl.DataFrame(
        {
            "foo": [1, 2, 3],
            "bar": [6.0, 7.0, 8.0],
            "ham": ["a", "b", "c"],
        }
    )
    out = df.with_column((pl.col("foo") % 2 == 1).alias("foo_odd")).sort(
        by=["foo", "foo_odd"]
    )
    assert out.shape == (3, 4)


def test_type_coercion_when_then_otherwise_2806() -> None:
    out = (
        pl.DataFrame({"names": ["foo", "spam", "spam"], "nrs": [1, 2, 3]})
        .select(
            [
                pl.when((pl.col("names") == "spam"))
                .then((pl.col("nrs") * 2))
                .otherwise(pl.lit("other"))
                .alias("new_col"),
            ]
        )
        .to_series()
    )
    expected = pl.Series("new_col", ["other", "4", "6"])
    assert out.to_list() == expected.to_list()

    # test it remains float32
    assert (
        pl.Series("a", [1.0, 2.0, 3.0], dtype=pl.Float32)
        .to_frame()
        .select(pl.when(pl.col("a") > 2.0).then(pl.col("a")).otherwise(0.0))
    ).to_series().dtype == pl.Float32


def test_repeat_expansion_in_groupby() -> None:
    out = (
        pl.DataFrame({"g": [1, 2, 2, 3, 3, 3]})
        .groupby("g", maintain_order=True)
        .agg(pl.repeat(1, pl.count()).cumsum())
        .to_dict(False)
    )
    assert out == {"g": [1, 2, 3], "literal": [[1], [1, 2], [1, 2, 3]]}


def test_agg_after_head() -> None:
    a = [1, 1, 1, 2, 2, 3, 3, 3, 3]

    df = pl.DataFrame({"a": a, "b": pl.arange(1, len(a) + 1, eager=True)})

    expected = pl.DataFrame({"a": [1, 2, 3], "b": [6, 9, 21]})

    for maintain_order in [True, False]:
        out = df.groupby("a", maintain_order=maintain_order).agg(
            [pl.col("b").head(3).sum()]
        )

        if not maintain_order:
            out = out.sort("a")

        assert out.frame_equal(expected)


def test_overflow_uint16_agg_mean() -> None:
    assert (
        pl.DataFrame(
            {
                "col1": ["A" for _ in range(1025)],
                "col3": [64 for i in range(1025)],
            }
        )
        .with_columns(
            [
                pl.col("col3").cast(pl.UInt16),
            ]
        )
        .groupby(["col1"])
        .agg(pl.col("col3").mean())
        .to_dict(False)
    ) == {"col1": ["A"], "col3": [64.0]}


def test_binary_on_list_agg_3345() -> None:
    df = pl.DataFrame(
        {
            "group": ["A", "A", "A", "B", "B", "B", "B"],
            "id": [1, 2, 1, 4, 5, 4, 6],
        }
    )

    assert (
        df.groupby(["group"], maintain_order=True)
        .agg(
            [
                (
                    (pl.col("id").unique_counts() / pl.col("id").len()).log()
                    * -1
                    * (pl.col("id").unique_counts() / pl.col("id").len())
                ).sum()
            ]
        )
        .to_dict(False)
    ) == {"group": ["A", "B"], "id": [0.6365141682948128, 1.0397207708399179]}


def test_maintain_order_after_sampling() -> None:
    # internally samples cardinality
    # check if the maintain_order kwarg is dispatched
    df = pl.DataFrame(
        {
            "type": ["A", "B", "C", "D", "A", "B", "C", "D"],
            "value": [1, 3, 2, 3, 4, 5, 3, 4],
        }
    )
    assert df.groupby("type", maintain_order=True).agg(pl.col("value").sum()).to_dict(
        False
    ) == {"type": ["A", "B", "C", "D"], "value": [5, 8, 5, 7]}


def test_sorted_groupby_optimization() -> None:
    df = pl.DataFrame({"a": np.random.randint(0, 5, 20)})

    # the sorted optimization should not randomize the
    # groups, so this is tests that we hit the sorted optimization
    for reverse in [True, False]:
        sorted_implicit = (
            df.with_column(pl.col("a").sort(reverse=reverse))
            .groupby("a")
            .agg(pl.count())
        )

        sorted_explicit = df.groupby("a").agg(pl.count()).sort("a", reverse=reverse)
        sorted_explicit.frame_equal(sorted_implicit)


def test_median_on_shifted_col_3522() -> None:
    df = pl.DataFrame(
        {
            "foo": [
                datetime(2022, 5, 5, 12, 31, 34),
                datetime(2022, 5, 5, 12, 47, 1),
                datetime(2022, 5, 6, 8, 59, 11),
            ]
        }
    )
    diffs = df.select(pl.col("foo").diff().dt.seconds())
    assert diffs.select(pl.col("foo").median()).to_series()[0] == 36828.5


def test_groupby_agg_equals_zero_3535() -> None:
    # setup test frame
    df = pl.DataFrame(
        data=[
            # note: the 'bb'-keyed values should clearly sum to 0
            ("aa", 10, None),
            ("bb", -10, 0.5),
            ("bb", 10, -0.5),
            ("cc", -99, 10.5),
            ("cc", None, 0.0),
        ],
        columns=[
            ("key", pl.Utf8),
            ("val1", pl.Int16),
            ("val2", pl.Float32),
        ],
    )
    # group by the key, aggregating the two numeric cols
    assert df.groupby(pl.col("key"), maintain_order=True).agg(
        [pl.col("val1").sum(), pl.col("val2").sum()]
    ).to_dict(False) == {
        "key": ["aa", "bb", "cc"],
        "val1": [10, 0, -99],
        "val2": [None, 0.0, 10.5],
    }


def test_arithmetic_in_aggregation_3739() -> None:
    def demean_dot() -> pl.Expr:
        x = pl.col("x")
        y = pl.col("y")
        x1 = x - x.mean()
        y1 = y - y.mean()
        return (x1 * y1).sum().alias("demean_dot")

    assert (
        pl.DataFrame(
            {
                "key": ["a", "a", "a", "a"],
                "x": [4, 2, 2, 4],
                "y": [2, 0, 2, 0],
            }
        )
        .groupby("key")
        .agg(
            [
                demean_dot(),
            ]
        )
    ).to_dict(False) == {"key": ["a"], "demean_dot": [0.0]}


def test_dtype_concat_3735() -> None:
    for dt in [
        pl.Int8,
        pl.Int16,
        pl.Int32,
        pl.Int64,
        pl.UInt8,
        pl.UInt16,
        pl.UInt32,
        pl.UInt64,
        pl.Float32,
        pl.Float64,
    ]:
        d1 = pl.DataFrame(
            [
                pl.Series("val", [1, 2], dtype=dt),
            ]
        )
        d2 = pl.DataFrame(
            [
                pl.Series("val", [3, 4], dtype=dt),
            ]
        )
        df = pl.concat([d1, d2])
        assert df.shape == (4, 1)

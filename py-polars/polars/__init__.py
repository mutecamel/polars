# flake8: noqa
import warnings

try:
    from polars.polars import version
except ImportError as e:  # pragma: no cover

    def version() -> str:
        return ""

    # this is only useful for documentation
    warnings.warn("polars binary missing!")

import polars.testing as testing
from polars.cfg import (  # flake8: noqa. We do not export in __all__
    Config,
    toggle_string_cache,
)
from polars.convert import from_arrow, from_dict, from_dicts, from_pandas, from_records
from polars.datatypes import (
    Boolean,
    Categorical,
    DataType,
    Date,
    Datetime,
    Duration,
    Field,
    Float32,
    Float64,
    Int8,
    Int16,
    Int32,
    Int64,
    List,
    Null,
    Object,
    PolarsDataType,
    Struct,
    Time,
    UInt8,
    UInt16,
    UInt32,
    UInt64,
    Utf8,
)
from polars.exceptions import (
    ArrowError,
    ComputeError,
    DuplicateError,
    NoDataError,
    NotFoundError,
    PanicException,
    SchemaError,
    ShapeError,
)
from polars.internals.expr import Expr
from polars.internals.frame import (  # flake8: noqa # TODO: remove need for wrap_df
    DataFrame,
    wrap_df,
)
from polars.internals.functions import arg_where, concat, date_range, get_dummies
from polars.internals.io import read_ipc_schema, read_parquet_schema
from polars.internals.lazy_frame import LazyFrame
from polars.internals.lazy_functions import _date as date
from polars.internals.lazy_functions import _datetime as datetime
from polars.internals.lazy_functions import (
    all,
    any,
    apply,
    arange,
    argsort_by,
    avg,
    col,
    collect_all,
    concat_list,
    concat_str,
    count,
    cov,
    duration,
    element,
    exclude,
    first,
    fold,
    format,
    groups,
    head,
    last,
    lit,
    map,
    map_binary,
    max,
    mean,
    median,
    min,
    n_unique,
    pearson_corr,
    quantile,
    repeat,
    select,
    spearman_rank_corr,
    std,
    struct,
    sum,
    tail,
)
from polars.internals.lazy_functions import to_list as list
from polars.internals.lazy_functions import var
from polars.internals.series import (  # flake8: noqa # TODO: remove need for wrap_s
    Series,
    wrap_s,
)
from polars.internals.whenthen import when
from polars.io import (
    read_avro,
    read_csv,
    read_excel,
    read_ipc,
    read_json,
    read_parquet,
    read_sql,
    scan_csv,
    scan_ds,
    scan_ipc,
    scan_parquet,
)
from polars.string_cache import StringCache
from polars.utils import threadpool_size

__all__ = [
    "exceptions",
    "NotFoundError",
    "ShapeError",
    "SchemaError",
    "ArrowError",
    "ComputeError",
    "NoDataError",
    "DataFrame",
    "Series",
    "LazyFrame",
    # polars.datatypes
    "DataType",
    "Int8",
    "Int16",
    "Int32",
    "Int64",
    "UInt8",
    "UInt16",
    "UInt32",
    "UInt64",
    "Float32",
    "Float64",
    "Boolean",
    "Utf8",
    "List",
    "Date",
    "Datetime",
    "Time",
    "Object",
    "Categorical",
    "Field",
    "Struct",
    # polars.io
    "read_csv",
    "read_parquet",
    "read_json",
    "read_sql",
    "read_ipc",
    "scan_csv",
    "scan_ipc",
    "scan_ds",
    "scan_parquet",
    "read_ipc_schema",
    "read_parquet_schema",
    "read_avro",
    # polars.stringcache
    "StringCache",
    # polars.config
    "Config",
    # polars.internal.when
    "when",
    # polars.internal.expr
    "Expr",
    # polars.internal.functions
    "arg_where",
    "concat",
    "date_range",
    "get_dummies",
    "repeat",
    # polars.internal.lazy_functions
    "col",
    "count",
    "std",
    "var",
    "max",
    "min",
    "sum",
    "mean",
    "avg",
    "median",
    "n_unique",
    "first",
    "last",
    "head",
    "tail",
    "lit",
    "pearson_corr",
    "spearman_rank_corr",
    "cov",
    "map",
    "apply",
    "map_binary",
    "fold",
    "any",
    "all",
    "groups",
    "quantile",
    "arange",
    "argsort_by",
    "concat_str",
    "concat_list",
    "collect_all",
    "exclude",
    "format",
    "datetime",  # named _datetime, see import above
    "date",  # name _date, see import above
    "list",  # named to_list, see import above
    "select",
    "var",
    # polars.convert
    "from_dict",
    "from_dicts",
    "from_records",
    "from_arrow",
    "from_pandas",
    # testing
    "testing",
    "threadpool_size",
]

__version__ = version()

import os

os.environ["POLARS_ALLOW_EXTENSION"] = "true"

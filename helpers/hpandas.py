"""
Import as:

import helpers.hpandas as hhpandas
"""
import logging
from typing import Any, Optional, Union

import pandas as pd

import helpers.dbg as hdbg
import helpers.printing as hprint

_LOG = logging.getLogger(__name__)


def dassert_index_is_datetime(
    df: pd.DataFrame, msg: Optional[str] = None, *args: Any
) -> None:
    """
    Ensure that the dataframe has an index containing datetimes.
    """
    # TODO(gp): Add support also for series.
    hdbg.dassert_isinstance(df, pd.DataFrame, msg, *args)
    hdbg.dassert_isinstance(df.index, pd.DatetimeIndex, msg, *args)


def dassert_strictly_increasing_index(
    obj: Union[pd.Index, pd.DataFrame, pd.Series],
    msg: Optional[str] = None,
    *args: Any,
) -> None:
    """
    Ensure that the dataframe has a strictly increasing index.
    """
    if isinstance(obj, pd.Index):
        index = obj
    else:
        index = obj.index
    # TODO(gp): Understand why mypy reports:
    #   error: "dassert" gets multiple values for keyword argument "msg"
    hdbg.dassert(index.is_monotonic_increasing, msg=msg, *args)  # type: ignore
    hdbg.dassert(index.is_unique, msg=msg, *args)  # type: ignore


# TODO(gp): Factor out common code related to extracting the index from several
#  pandas data structures.
# TODO(gp): Not sure it's used or useful?
def dassert_monotonic_index(
    obj: Union[pd.Index, pd.DataFrame, pd.Series],
    msg: Optional[str] = None,
    *args: Any,
) -> None:
    """
    Ensure that the dataframe has a strictly increasing or decreasing index.
    """
    if isinstance(obj, pd.Index):
        index = obj
    else:
        index = obj.index
    # TODO(gp): Understand why mypy reports:
    #   error: "dassert" gets multiple values for keyword argument "msg"
    cond = index.is_monotonic_increasing or index.is_monotonic_decreasing
    hdbg.dassert(cond, msg=msg, *args)  # type: ignore
    hdbg.dassert(index.is_unique, msg=msg, *args)  # type: ignore


def resample_index(index: pd.DatetimeIndex, frequency: str) -> pd.DatetimeIndex:
    """
    Resample `DatetimeIndex`.

    :param index: `DatetimeIndex` to resample
    :param frequency: frequency from `pd.date_range()` to resample to
    :return: resampled `DatetimeIndex`
    """
    hdbg.dassert_isinstance(index, pd.DatetimeIndex)
    hdbg.dassert(
        index.is_unique,
        msg="Index must have only unique values"
    )
    min_date = index.min()
    max_date = index.max()
    resampled_index = pd.date_range(
        start=min_date,
        end=max_date,
        freq=frequency,
    )
    if len(resampled_index) > len(index):
        # Downsampling case.
        _LOG.info(
            "Index length increased by %s = %s - %s",
            len(resampled_index) - len(index),
            len(resampled_index),
            len(index),
        )
    elif len(resampled_index) < len(index):
        # Upsampling case.
        _LOG.info(
            "Index length decreased by %s = %s - %s",
            len(index) - len(resampled_index),
            len(index),
            len(resampled_index),
        )
    else:
        _LOG.info(
            "Index length=%s has not changes",
            len(index)
        )
    return resampled_index


def resample_df(df: pd.DataFrame, frequency: str) -> pd.DataFrame:
    """
    Resample `DataFrame`.

    Place NaN in locations having no value in the previous index.

    :param df: `DataFrame` to resample
    :param frequency: frequency from `pd.date_range()` to resample to
    :return: resampled `DataFrame`
    """
    hdbg.dassert_isinstance(df, pd.DataFrame)
    resampled_index = resample_index(df.index, frequency)
    df_reindex = df.reindex(resampled_index)
    return df_reindex


def drop_duplicates(
    data: Union[pd.Series, pd.DataFrame], *args: Any, **kwargs: Any,
) -> Union[pd.Series, pd.DataFrame]:
    """
    Wrapper around `pandas.drop_duplicates()`.

    See the official docs:
        - https://pandas.pydata.org/docs/reference/api/pandas.Series.drop_duplicates.html
        - https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.drop_duplicates.html

    :return: data w/o duplicates
    """
    _LOG.debug("args=%s, kwargs=%s", str(args), str(kwargs))
    num_rows_before = data.shape[0]
    data_no_dups = data.drop_duplicates(*args, **kwargs)
    num_rows_after = data_no_dups.shape[0]
    if num_rows_before != num_rows_after:
        _LOG.warning(
            "Removed %s rows",
            hprint.perc(num_rows_before - num_rows_after, num_rows_before),
        )
    return data_no_dups

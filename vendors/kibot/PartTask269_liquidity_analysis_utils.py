import functools
import logging
import os
from typing import Callable, Dict, Optional

import matplotlib.pyplot as plt
import pandas as pd

import helpers.dbg as dbg
import helpers.s3 as hs3
import vendors.cme.read as cmer
import vendors.kibot.utils as kut

_LOG = logging.getLogger(__name__)

KIBOT_VOL = "vol"


def get_sum_prices(
    price_df_dict: Dict[str, pd.DataFrame], price_col: str
) -> pd.DataFrame:
    """
    Get sum of the prices for each symbol.

    :param price_df_dict: {symbol: prices_for_symbol_df}
    :param price_col: The name of the price column
    :return: pd.DataFrame indexed by symbol
    """
    prices_sum_df = _get_prices(price_df_dict, price_col, "sum")
    return prices_sum_df


def get_mean_prices(
    price_df_dict: Dict[str, pd.DataFrame], price_col: str
) -> pd.DataFrame:
    """
    Get mean of the prices for each symbol.

    :param price_df_dict: {symbol: prices_for_symbol_df}
    :param price_col: The name of the price column
    :return: pd.DataFrame indexed by symbol
    """
    prices_mean_df = _get_prices(price_df_dict, price_col, "mean")
    return prices_mean_df


def get_kibot_reader(
    frequency: str, symbol: str, n_rows: Optional[int] = None
) -> Callable:
    dbg.dassert_in(
        frequency,
        ["D", "T", "min"],
        "Only daily ('D') and minutely ('T', 'min') frequencies are supported.",
    )
    if frequency in ["T", "min"]:
        dir_path = os.path.join(
            hs3.get_path(), "kibot/All_Futures_Continuous_Contracts_1min"
        )
    elif frequency == "D":
        dir_path = os.path.join(
            hs3.get_path(), "kibot/All_Futures_Continuous_Contracts_daily"
        )
    else:
        raise ValueError("The %s frequency is not supported", frequency)
    file_name = os.path.join(dir_path, f"{symbol}.csv.gz")
    reader = functools.partial(kut.read_data, file_name, nrows=n_rows)
    return reader


def read_kibot_prices(
    frequency: str, symbol: str, n_rows: Optional[int]
) -> pd.DataFrame:
    reader = get_kibot_reader(frequency, symbol, n_rows)
    prices = reader()
    return prices


def _get_prices(
    price_df_dict: Dict[str, pd.DataFrame], price_col: str, agg_func: str
) -> pd.DataFrame:
    """
    Get grouped prices for each symbol.

    :param price_df_dict: {symbol: prices_for_symbol_df}
    :param price_col: The name of the price column
    :param agg_func: The name of the aggregation function that needs to
        be applied to the prices for each symbol
    :return: pd.DataFrame indexed by symbol
    """
    price_dict = {
        symbol: getattr(prices[price_col], agg_func)()
        for symbol, prices in price_df_dict.items()
    }
    price_df = pd.DataFrame.from_dict(
        price_dict, orient="index", columns=[f"{agg_func}_{price_col}"]
    )
    price_df.index.name = "symbol"
    return price_df


class TimeSeriesStudy:
    """
    Perform a basic study of daily and minutely time series.

    - Read daily and minutely time series
    - Plot daily and minutely time series for column
        - by year
        - by month
        - by day of week
        - by hour
    """

    def __init__(
        self,
        data_reader: Callable[[], pd.DataFrame],
        col_name: str,
        freq_name: str,
        data_name: Optional[str] = None,
        resample_freq: Optional[str] = None,
        resample_agg_func: Optional[str] = None,
    ):
        """
        :param data_reader: A function that returns a pd.DataFrame with
            the col_name column and a datetime index
        :param col_name: The name of the time series column
        :param freq_name: The name of the data frequency to add to plot
            titles (for example, 'daily').
        :param data_name: The name of the data to add to plot titles
            (for example, symbol).
        :param resample_freq: pandas frequency passed to the resample
            function. The list of supported frequencies:
            https://pandas.pydata.org/pandas-docs/stable/user_guide/timeseries.html#offset-aliases
        :param resample_agg_func: Aggregation function applied to the
            resample
        """
        self._data_reader = data_reader
        self.data = self._data_reader()
        self._check_data_index()
        self._col_name = col_name
        self._data_name = data_name
        self.time_series = self.data[self._col_name]
        self.freq_name = freq_name
        self.resample_freq = resample_freq
        self.agg_func = resample_agg_func
        if self.resample_freq:
            self.time_series = getattr(
                self.time_series.resample(resample_freq), self.agg_func
            )()

    def plot_time_series(self,):
        self.time_series.plot()
        plt.title(
            f"{self.freq_name.capitalize()} {self._col_name}"
            f"{self._title_suffix}"
        )
        plt.xticks(
            self.time_series.resample("YS").sum().index,
            ha="right",
            rotation=30,
            rotation_mode="anchor",
        )
        plt.show()

    def plot_changes_by_year(self, sharey=False):
        yearly_resample = self.time_series.resample("y")
        fig, axis = plt.subplots(
            len(yearly_resample),
            figsize=(20, 5 * len(yearly_resample)),
            sharey=sharey,
        )
        for i, year_ts in enumerate(yearly_resample):
            year_ts[1].plot(ax=axis[i], title=year_ts[0].year)
        plt.suptitle(
            f"{self.freq_name.capitalize()} {self._col_name} changes by year"
            f"{self._title_suffix}",
            y=1.005,
        )
        plt.tight_layout()

    def plot_mean_day_of_month(self):
        self.time_series.groupby(self.time_series.index.day).mean().plot(
            kind="bar", rot=0
        )
        plt.xlabel("day of month")
        plt.title(
            f"Mean {self.freq_name} {self._col_name} on different days of "
            f"month{self._title_suffix}"
        )
        plt.show()

    def plot_mean_day_of_week(self):
        self.time_series.groupby(self.time_series.index.dayofweek).mean().plot(
            kind="bar", rot=0
        )
        plt.xlabel("day of week")
        plt.title(
            f"Mean {self.freq_name} {self._col_name} on different days of "
            f"week{self._title_suffix}"
        )
        plt.show()

    def _check_data_index(self):
        assert isinstance(
            self.data.index, pd.DatetimeIndex
        ), "The index should have pd.DatetimeIndex format."
        dbg.dassert_monotonic_index(
            self.data.index, "The index should be monotonic increasing"
        )

    @property
    def _title_suffix(self):
        if self._data_name is not None:
            return f" for {self._data_name}"
        else:
            return ""


class TimeSeriesDailyStudy(TimeSeriesStudy):
    def __init__(
        self,
        data_reader: Callable[[], pd.DataFrame],
        col_name: str,
        freq_name: Optional[str] = None,
        data_name: Optional[str] = None,
        resample_freq: Optional[str] = None,
        resample_agg_func: Optional[str] = None,
    ):
        if not freq_name:
            freq_name = "daily"
        super(TimeSeriesDailyStudy, self).__init__(
            data_reader=data_reader,
            col_name=col_name,
            freq_name=freq_name,
            data_name=data_name,
            resample_freq=resample_freq,
            resample_agg_func=resample_agg_func,
        )

    def execute(self):
        self.plot_time_series()
        self.plot_changes_by_year()
        self.plot_mean_day_of_month()
        self.plot_mean_day_of_week()


class TimeSeriesMinStudy(TimeSeriesStudy):
    def __init__(
        self,
        data_reader: Callable[[], pd.DataFrame],
        col_name: str,
        freq_name: Optional[str] = None,
        data_name: Optional[str] = None,
        resample_freq: Optional[str] = None,
        resample_agg_func: Optional[str] = None,
    ):
        if not freq_name:
            freq_name = "minutely"
        super(TimeSeriesMinStudy, self).__init__(
            data_reader=data_reader,
            col_name=col_name,
            freq_name=freq_name,
            data_name=data_name,
            resample_freq=resample_freq,
            resample_agg_func=resample_agg_func,
        )

    def execute(self):
        self.plot_time_series()
        self.plot_changes_by_year()
        self.plot_mean_day_of_week()
        self.plot_minutely_hour()

    def plot_minutely_hour(self):
        self.time_series.groupby(self.time_series.index.hour).mean().plot(
            kind="bar", rot=0
        )
        plt.title(
            f"Mean {self._col_name} during different hours"
            f"{self._title_suffix}"
        )
        plt.xlabel("hour")
        plt.show()


class ProductSpecs:
    """
    Read product specs, get data by symbol or product group.
    """

    def __init__(self):
        self.product_specs = cmer.read_product_specs()

    def get_metadata_symbol(self, symbol):
        return self.product_specs.loc[self.product_specs["Globex"] == symbol]

    def get_trading_hours(self, symbol):
        # Only nans are repeated, so we can return the first element.
        return self.get_metadata_symbol(symbol)["Trading Hours"].iloc[0]

    def get_product_group(self, symbol):
        return self.get_metadata_symbol(symbol)["Product Group"].iloc[0]

    def get_specs_product_group(self, product_group):
        return self.product_specs.set_index("Product Group").loc[product_group]

    def get_symbols_product_group(self, product_group):
        return self.get_specs_product_group(product_group)["Globex"].values

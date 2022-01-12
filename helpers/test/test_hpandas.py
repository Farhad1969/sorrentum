import io
import logging
from typing import Any

import pandas as pd

import helpers.hpandas as hpandas
import helpers.hprint as hprint
import helpers.hunit_test as hunitest

_LOG = logging.getLogger(__name__)


class Test_to_series1(hunitest.TestCase):
    def helper(self, n: int, exp: str) -> None:
        vals = list(range(n))
        df = pd.DataFrame([vals], columns=[f"a{i}" for i in vals])
        df = df.T
        _LOG.debug("df=\n%s", df)
        srs = hpandas.to_series(df)
        _LOG.debug("srs=\n%s", srs)
        act = str(srs)
        self.assert_equal(act, exp, dedent=True, fuzzy_match=True)

    def test1(self) -> None:
        n = 0
        exp = r"""
        Series([], dtype: float64)
        """
        self.helper(n, exp)

    def test2(self) -> None:
        n = 1
        exp = r"""
        a0    0
        dtype: int64"""
        self.helper(n, exp)

    def test3(self) -> None:
        n = 5
        exp = r"""
        a0    0
        a1    1
        a2    2
        a3    3
        a4    4
        Name: 0, dtype: int64"""
        self.helper(n, exp)


# #############################################################################


class Test_trim_df1(hunitest.TestCase):
    def get_df(self, *args: Any, **kwargs: Any) -> pd.DataFrame:
        """
        Return a df where the CSV txt is read verbatim without inferring dates.

        The `start_time` column is thus a str.
        """

        txt = """
        ,start_time,egid,close
        4,2022-01-04 21:38:00.000000,13684,1146.48
        8,2022-01-04 21:38:00.000000,17085,179.45
        14,2022-01-04 21:37:00.000000,13684,1146.26
        18,2022-01-04 21:37:00.000000,17085,179.42
        24,2022-01-04 21:36:00.000000,13684,1146.0
        27,2022-01-04 21:36:00.000000,17085,179.46
        34,2022-01-04 21:35:00.000000,13684,1146.0
        38,2022-01-04 21:35:00.000000,17085,179.42
        40,2022-01-04 21:34:00.000000,17085,179.42
        44,2022-01-04 21:34:00.000000,13684,1146.0
        """
        txt = hprint.dedent(txt)
        df = pd.read_csv(io.StringIO(txt), *args, index_col=0, **kwargs)
        return df

    def test_types1(self):
        """
        Check the types of a df coming from `read_csv()`.

        The timestamps in `start_time` are left as strings.
        """
        df = self.get_df()
        #
        act = hprint.df_to_short_str("df", df, print_dtypes=True)
        exp = r"""# df=
        df.index in [4, 44]
        df.columns=start_time,egid,close
        df.shape=(10, 3)
        df.type=
                         index:      int64     <class 'numpy.int64'> 4
                    start_time:     object             <class 'str'> 2022-01-04 21:38:00.000000
                          egid:      int64     <class 'numpy.int64'> 13684
                         close:    float64   <class 'numpy.float64'> 1146.48
                            start_time   egid    close
        4   2022-01-04 21:38:00.000000  13684  1146.48
        8   2022-01-04 21:38:00.000000  17085   179.45
        14  2022-01-04 21:37:00.000000  13684  1146.26
        ...
        38  2022-01-04 21:35:00.000000  17085   179.42
        40  2022-01-04 21:34:00.000000  17085   179.42
        44  2022-01-04 21:34:00.000000  13684  1146.00"""
        self.assert_equal(act, exp, fuzzy_match=True)

    def get_df_with_parse_dates(self) -> pd.DataFrame:
        """
        Read the CSV parsing `start_time` as timestamps.

        The inferred type is a nasty `datetime64` which is not as well-
        behaved as our beloved `pd.Timestamp`.
        """
        df = self.get_df(parse_dates=["start_time"])
        return df

    def test_types2(self):
        """
        Check the types of a df coming from `read_csv()` forcing parsing some
        values as dates.
        """
        df = self.get_df_with_parse_dates()
        # Check.
        act = hprint.df_to_short_str("df", df, print_dtypes=True)
        exp = r"""# df=
        df.index in [4, 44]
        df.columns=start_time,egid,close
        df.shape=(10, 3)
        df.type=
                         index:      int64     <class 'numpy.int64'> 4
                    start_time: datetime64[ns] <class 'numpy.datetime64'> 2022-01-04T21:38:00.000000000
                          egid:      int64     <class 'numpy.int64'> 13684
                         close:    float64   <class 'numpy.float64'> 1146.48
                    start_time   egid    close
        4  2022-01-04 21:38:00  13684  1146.48
        8  2022-01-04 21:38:00  17085   179.45
        14 2022-01-04 21:37:00  13684  1146.26
        ...
        38 2022-01-04 21:35:00  17085   179.42
        40 2022-01-04 21:34:00  17085   179.42
        44 2022-01-04 21:34:00  13684  1146.00"""
        self.assert_equal(act, exp, fuzzy_match=True)

    def get_df_with_tz_timestamp(self) -> pd.DataFrame:
        """
        Force the column parsed as `datetime64` into a tz-aware object.

        The resulting object is a `datetime64[ns, tz]`.
        """
        df = self.get_df_with_parse_dates()
        # Apply the tz.
        col_name = "start_time"
        df[col_name] = (
            df[col_name].dt.tz_localize("UTC").dt.tz_convert("America/New_York")
        )
        df[col_name] = pd.to_datetime(df[col_name])
        return df

    def test_types3(self):
        """
        Check the types of a df coming from `read_csv()` after conversion to
        tz-aware objects.
        """
        df = self.get_df_with_tz_timestamp()
        # Check.
        act = hprint.df_to_short_str("df", df, print_dtypes=True)
        exp = r"""# df=
        df.index in [4, 44]
        df.columns=start_time,egid,close
        df.shape=(10, 3)
        df.type=
                         index:      int64     <class 'numpy.int64'> 4
                    start_time: datetime64[ns, America/New_York] <class 'numpy.datetime64'> 2022-01-04T21:38:00.000000000
                          egid:      int64     <class 'numpy.int64'> 13684
                         close:    float64   <class 'numpy.float64'> 1146.48
                          start_time   egid    close
        4  2022-01-04 16:38:00-05:00  13684  1146.48
        8  2022-01-04 16:38:00-05:00  17085   179.45
        14 2022-01-04 16:37:00-05:00  13684  1146.26
        ...
        38 2022-01-04 16:35:00-05:00  17085   179.42
        40 2022-01-04 16:34:00-05:00  17085   179.42
        44 2022-01-04 16:34:00-05:00  13684  1146.00"""
        self.assert_equal(act, exp, fuzzy_match=True)

    def test_trim_df1(self):
        """
        In general one can't filter a df with columns represented as `str`
        using `pd.Timestamp` (either tz-aware or tz-naive).

        Pandas helps us when filtering the index doing some conversion
        for us. When it's a column, we have to handle it ourselves:
        `trim_df` does that by converting the columns in `pd.Timestamp`.
        """
        df = self.get_df()
        # Run.
        ts_col_name = "start_time"
        start_ts = pd.Timestamp("2022-01-04 21:35:00")
        end_ts = pd.Timestamp("2022-01-04 21:38:00")
        left_close = True
        right_close = True
        df_trim = hpandas.trim_df(
            df, ts_col_name, start_ts, end_ts, left_close, right_close
        )
        # Check.
        act = hprint.df_to_short_str("df_trim", df_trim, print_dtypes=True)
        exp = r"""# df_trim=
        df.index in [4, 38]
        df.columns=start_time,egid,close
        df.shape=(8, 3)
        df.type=
                         index:      int64     <class 'numpy.int64'> 4
                    start_time:     object             <class 'str'> 2022-01-04 21:38:00.000000
                          egid:      int64     <class 'numpy.int64'> 13684
                         close:    float64   <class 'numpy.float64'> 1146.48
                            start_time   egid    close
        4   2022-01-04 21:38:00.000000  13684  1146.48
        8   2022-01-04 21:38:00.000000  17085   179.45
        14  2022-01-04 21:37:00.000000  13684  1146.26
        ...
        27  2022-01-04 21:36:00.000000  17085   179.46
        34  2022-01-04 21:35:00.000000  13684  1146.00
        38  2022-01-04 21:35:00.000000  17085   179.42"""
        self.assert_equal(act, exp, fuzzy_match=True)

    def test_trim_df2(self):
        """
        Trim a df with a column that is `datetime64` without tz using a
        `pd.Timestamp` without tz.

        This operation is valid.
        """
        df = self.get_df_with_parse_dates()
        # Run.
        ts_col_name = "start_time"
        start_ts = pd.Timestamp("2022-01-04 21:35:00")
        end_ts = pd.Timestamp("2022-01-04 21:38:00")
        left_close = True
        right_close = True
        df_trim = hpandas.trim_df(
            df, ts_col_name, start_ts, end_ts, left_close, right_close
        )
        # Check.
        act = hprint.df_to_short_str("df_trim", df_trim, print_dtypes=True)
        exp = r"""# df_trim=
        df.index in [4, 38]
        df.columns=start_time,egid,close
        df.shape=(8, 3)
        df.type=
                         index:      int64     <class 'numpy.int64'> 4
                    start_time: datetime64[ns] <class 'numpy.datetime64'> 2022-01-04T21:38:00.000000000
                          egid:      int64     <class 'numpy.int64'> 13684
                         close:    float64   <class 'numpy.float64'> 1146.48
                    start_time   egid    close
        4  2022-01-04 21:38:00  13684  1146.48
        8  2022-01-04 21:38:00  17085   179.45
        14 2022-01-04 21:37:00  13684  1146.26
        ...
        27 2022-01-04 21:36:00  17085   179.46
        34 2022-01-04 21:35:00  13684  1146.00
        38 2022-01-04 21:35:00  17085   179.42"""
        self.assert_equal(act, exp, fuzzy_match=True)

    def test_trim_df3(self):
        """
        Trim a df with a column that is `datetime64` with tz vs a `pd.Timestamp
        with tz.

        This operation is valid.
        """
        df = self.get_df_with_tz_timestamp()
        # Run.
        ts_col_name = "start_time"
        start_ts = pd.Timestamp("2022-01-04 21:35:00", tz="UTC")
        end_ts = pd.Timestamp("2022-01-04 21:38:00", tz="UTC")
        left_close = True
        right_close = True
        df_trim = hpandas.trim_df(
            df, ts_col_name, start_ts, end_ts, left_close, right_close
        )
        # Check.
        act = hprint.df_to_short_str("df_trim", df_trim, print_dtypes=True)
        exp = r"""# df_trim=
        df.index in [4, 38]
        df.columns=start_time,egid,close
        df.shape=(8, 3)
        df.type=
                         index:      int64     <class 'numpy.int64'> 4
                    start_time: datetime64[ns, America/New_York] <class 'numpy.datetime64'> 2022-01-04T21:38:00.000000000
                          egid:      int64     <class 'numpy.int64'> 13684
                         close:    float64   <class 'numpy.float64'> 1146.48
                          start_time   egid    close
        4  2022-01-04 16:38:00-05:00  13684  1146.48
        8  2022-01-04 16:38:00-05:00  17085   179.45
        14 2022-01-04 16:37:00-05:00  13684  1146.26
        ...
        27 2022-01-04 16:36:00-05:00  17085   179.46
        34 2022-01-04 16:35:00-05:00  13684  1146.00
        38 2022-01-04 16:35:00-05:00  17085   179.42"""
        self.assert_equal(act, exp, fuzzy_match=True)

    def test_trim_df4(self):
        """
        Trim a df with a column that is `datetime64` with tz vs a `pd.Timestamp
        without tz.

        This operation is invalid and we expect an assertion.
        """
        df = self.get_df_with_tz_timestamp()
        # Run.
        ts_col_name = "start_time"
        start_ts = pd.Timestamp("2022-01-04 21:35:00")
        end_ts = pd.Timestamp("2022-01-04 21:38:00")
        left_close = True
        right_close = True
        with self.assertRaises(AssertionError) as cm:
            hpandas.trim_df(
                df, ts_col_name, start_ts, end_ts, left_close, right_close
            )
        # Check.
        act = str(cm.exception)
        exp = r"""
        * Failed assertion *
        'True'
        ==
        'False'
        datetime1='2022-01-04 16:38:00-05:00' and datetime2='2022-01-04 21:35:00' are not compatible"""
        self.assert_equal(act, exp, fuzzy_match=True)
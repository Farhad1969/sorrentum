"""
Import as:

import oms.portfolio as omportfo
"""
import collections
import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

import core.dataflow.price_interface as cdtfprint
import helpers.dbg as hdbg
import helpers.printing as hprint
import oms.order as omorder

_LOG = logging.getLogger(__name__)


# TODO(gp): Add an abstract interface and other implementations.
class Portfolio:
    """
    Store tables with the following info:

    - holdings over time
        - how many shares of each asset are owned at any time
        - cash is treated as any other asset to keep code uniform
    - orders executed over time
        - what orders were executed, for how many shares, and at how much

    The tables are indexed by knowledge time, i.e., when this information became
    known by this object.
    """

    # ID of asset representing cash.
    CASH_ID: int = -1

    def __init__(
        self,
        # TODO(GP): Add docstrings for these.
        strategy_id: str,
        account: str,
        #
        price_interface: cdtfprint.AbstractPriceInterface,
        # TODO(gp): -> _column -> _col_name
        asset_id_column: str,
        # TODO(gp): -> mark_to_market_col_name
        price_column: str,
        #
        initial_cash: float,
        initial_timestamp: pd.Timestamp,
        # TODO(Paul): Add ability to initialize holdings.
    ):
        """
        Constructor.

        :param asset_id_column: column name in the output df of `price_interface`
            storing the asset id
        :param price_column: column name used to mark holdings to market
        """
        _LOG.debug(
            hprint.to_str(
                "strategy_id account asset_id_column price_column initial_cash initial_timestamp"
            )
        )
        self._strategy_id = strategy_id
        self._account = account
        #
        hdbg.dassert_issubclass(price_interface, cdtfprint.AbstractPriceInterface)
        self._price_interface = price_interface
        self._asset_id_column = asset_id_column
        self._price_column = price_column
        # Initialize dataframe with holdings over time.
        hdbg.dassert_lt(0, initial_cash)
        row = [Portfolio.CASH_ID, initial_cash]
        # TODO(gp): Check that initial_timestamp is pd.Timestamp.
        # Store `id` and `position`.
        self._holdings_columns = ["asset_id", "curr_num_shares"]
        self._holdings = pd.DataFrame(
            [row], index=[initial_timestamp], columns=self._holdings_columns
        )
        # Initialize dataframe with executed orders.
        # TODO(Paul): Should these come from the `Order` class itself?
        self._order_columns = [
            # Order corresponding to the change in position.
            "order_id",
            # Info from the order.
            "creation_timestamp",
            "asset_id",
            "type_",
            "start_timestamp",
            "end_timestamp",
            "num_shares",
            # Info about the order execution.
            "num_shares_filled",
            "execution_price",
            # Holdings after this order was executed.
            "holdings+1",
            # Amount of cash after this order was executed.
            "cash+1",
        ]
        # We start with an empty row in `orders` to keep it aligned with `holdings`.
        self._orders = pd.DataFrame(
            [], index=[initial_timestamp], columns=self._order_columns
        )

    def __str__(self) -> str:
        act = []
        act.append("# holdings=\n%s" % hprint.dataframe_to_str(self.holdings))
        act.append("# orders=\n%s" % hprint.dataframe_to_str(self.orders))
        act = "\n".join(act)
        return act

    @property
    def holdings(self) -> pd.DataFrame:
        return self._holdings

    @property
    def orders(self) -> pd.DataFrame:
        return self._orders

    def get_last_timestamp(self) -> pd.Timestamp:
        """
        Get the last time known to Portfolio.
        """
        # TODO(gp): This is not true because holdings contain also data for one
        #  interval ahead.
        # hdbg.dassert_eq(self._holdings.index.max(), self._orders.index.max())
        return self._holdings.index.max()

    def get_holdings(
        self,
        timestamp: pd.Timestamp,
        asset_id: Optional[Any],
        *,
        exclude_cash: bool = False,
    ) -> pd.DataFrame:
        """
        Return the holdings in shares at `timestamp` for one or all the assets.

        :param asset_id: consider only a specific asset. `None` means all holdings.
        :param exclude_cash: exclude cash from the holdings
        :return: a dataframe with asset id and num_shares
            ```
                                       asset_id  curr_num_shares
            2000-01-01 09:35:00-05:00      -1.0        1000000.0
            ```

        - empty dataframe if there are no holdings for the requested timestamp
        `timestamp`
        """
        _LOG.debug(hprint.to_str("timestamp asset_id exclude_cash"))
        _LOG.debug("holdings=\n%s", hprint.dataframe_to_str(self._holdings))
        if timestamp not in self._holdings.index:
            _LOG.debug("Timestamp=`%s` not found in holdings index", timestamp)
            empty_holdings = pd.DataFrame(
                [], index=[], columns=self._holdings_columns
            )
            return empty_holdings
        holdings = self._holdings.loc[timestamp]
        if isinstance(holdings, pd.Series):
            holdings = holdings.to_frame().T
        _LOG.debug("holdings=%s\n%s", str(holdings.shape), holdings)
        hdbg.dassert(
            not holdings.empty,
            "Timestamp=`%s` found in index but filtered holdings are empty!",
            timestamp,
        )
        hdbg.dassert_no_duplicates(holdings["asset_id"])
        # Filter by asset_id, if needed.
        if asset_id is not None:
            _LOG.debug("Filtering by asset_id: holdings=\n%s", holdings)
            mask = holdings["asset_id"] == asset_id
            _LOG.debug("mask=\n%s", mask)
            holdings = holdings[mask]
            if holdings.empty:
                _LOG.debug(
                    "No holdings available at timestamp=`%s` for asset_id=`%s`",
                    timestamp,
                    asset_id,
                )
        # Exclude cash, if needed.
        if exclude_cash:
            _LOG.debug("exclude_cash: holdings=\n%s", holdings)
            hdbg.dassert_ne(
                asset_id,
                self.CASH_ID,
                "You cannot request cash (asset_id=`%s`) and simultaneously request to exclude it",
                asset_id,
            )
            mask = holdings["asset_id"] != self.CASH_ID
            _LOG.debug("mask=\n%s", mask)
            holdings = holdings[mask]
            if holdings.empty:
                _LOG.debug(
                    "No non-cash holdings available at timestamp=`%s`", timestamp
                )
        return holdings

    def get_holdings_as_scalar(
        self,
        timestamp: pd.Timestamp,
        asset_id: int,
    ) -> float:
        """
        Return the number of shares held for a given asset.

        For cash, this is the same as the cash value.
        """
        holdings = self.get_holdings(timestamp, asset_id=asset_id)
        _LOG.debug("holdings=\n%s", holdings)
        if holdings.empty:
            ret = 0
        else:
            ret = holdings["curr_num_shares"].values[0]
        _LOG.debug("ret=%s", ret)
        return ret

    def mark_holdings_to_market(
        self, timestamp: pd.Timestamp, holdings: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Mark holdings to market prices available at `timestamp`.

        :param holdings: a subset of the `holdings` df to annotate with price
            information
        :return: return `holdings` df decorated with `value`, `position`, and `price`
        """
        _LOG.debug(
            "\n%s",
            hprint.frame(
                "mark_holdings_to_market: timestamp=%s" % timestamp, char1="<"
            ),
        )
        _LOG.debug("holdings=\n%s", hprint.dataframe_to_str(holdings))
        # Get the prices for the assets.
        asset_ids = holdings["asset_id"].unique()
        hdbg.dassert(np.isfinite(asset_ids).all())
        _LOG.debug("asset_ids=%s", asset_ids)
        # TODO(gp): This should not be hardwired.
        timestamp_col_name = "end_datetime"
        price_df = self._price_interface.get_data_at_timestamp(
            timestamp, timestamp_col_name, asset_ids
        )
        hdbg.dassert_eq(
            price_df.shape[0], len(asset_ids), msg="Some assets have no price"
        )
        _LOG.debug("price_df=\n%s", hprint.dataframe_to_str(price_df))
        # Extract subset of price information.
        columns = [self._asset_id_column, self._price_column]
        hdbg.dassert_is_subset(columns, price_df.columns)
        price_df = price_df[columns]
        # Merge the holdings with the prices.
        result_df = pd.merge(
            holdings,
            price_df,
            how="outer",
            left_on="asset_id",
            right_on=self._asset_id_column,
        )
        result_df.rename(columns={self._price_column: "price"}, inplace=True)
        # Compute the value.
        result_df["value"] = result_df["curr_num_shares"] * result_df["price"]
        # TODO(gp): We should have no nans in res_df["value"].
        return result_df

    def get_net_wealth(self, timestamp: pd.Timestamp) -> float:
        """
        Return the net value of all holdings and cash at time `timestamp`.
        """
        _LOG.debug(
            "\n%s",
            hprint.frame("get_net_wealth: timestamp=%s" % timestamp, char1="<"),
        )
        portfolio_characteristics = self.get_characteristics(timestamp)
        net_wealth = portfolio_characteristics["net_wealth"]
        return net_wealth

    # TODO(Paul): Think of a better name.
    def get_characteristics(self, timestamp: pd.Timestamp) -> pd.Series:
        """
        Return asset/cash values, net wealth, exposure, and leverage.
        """
        _LOG.debug(
            "\n%s",
            hprint.frame(
                "get_characteristics: timestamp=%s" % timestamp, char1="<"
            ),
        )
        # Mark the current holdings to market.
        asset_id = None
        holdings = self.get_holdings(timestamp, asset_id, exclude_cash=True)
        holdings = self.mark_holdings_to_market(timestamp, holdings)
        # Compute value of holdings.
        holdings_net_value = holdings["value"].sum()
        _LOG.debug("-> holdings_net_value=%s", holdings_net_value)
        hdbg.dassert(
            np.isfinite(holdings_net_value),
            "holdings_net_value=%s",
            holdings_net_value,
        )
        # Get the cash available.
        cash = self.get_holdings_as_scalar(timestamp, asset_id=self.CASH_ID)
        hdbg.dassert(np.isfinite(cash), "cash=%s", cash)
        # Cash should always be positive.
        hdbg.dassert_lte(0.0, cash, "cash=%s", cash)
        _LOG.debug("-> cash=%s", cash)
        # Compute the net wealth (AKA "total value" AKA "NAV").
        net_wealth = holdings_net_value + cash
        hdbg.dassert(np.isfinite(net_wealth), "net_value=%s", net_wealth)
        _LOG.debug("-> net_wealth=%s", net_wealth)
        # Compute the gross exposure.
        gross_exposure = holdings["value"].abs().sum()
        # Compute the portfolio leverage.
        leverage = gross_exposure / net_wealth
        dict_ = {
            "net_asset_holdings": holdings_net_value,
            "cash": cash,
            "net_wealth": net_wealth,
            "gross_exposure": gross_exposure,
            "leverage": leverage,
        }
        return pd.Series(dict_, name=timestamp)

    def place_orders(
        self,
        timestamp: pd.Timestamp,
        next_timestamp: pd.Timestamp,
        orders: List[omorder.Order],
    ) -> None:
        """
        Change state of the portfolio based on the given orders.
        """
        _LOG.debug(
            "\n%s",
            hprint.frame("place_orders: timestamp=%s" % timestamp, char1="<"),
        )
        hdbg.dassert_isinstance(timestamp, pd.Timestamp)
        hdbg.dassert_isinstance(next_timestamp, pd.Timestamp)
        _LOG.debug(
            "before place_orders: orders=\n%s",
            hprint.dataframe_to_str(self._orders),
        )
        # TODO(gp): Check that orders are all for different asset_ids.
        last_timestamp = self.get_last_timestamp()
        hdbg.dassert_lte(last_timestamp, timestamp)
        # Get the current available cash.
        cash = self.get_holdings_as_scalar(last_timestamp, self.CASH_ID)
        # Process the orders.
        orders_rows = []
        holdings_rows = []
        for order in orders:
            _LOG.debug("# Processing order=%s", order)
            orders_row: Dict[str, Any] = collections.OrderedDict()
            hdbg.dassert_eq(
                order.end_timestamp,
                next_timestamp,
                "The order %s doesn't end at next_timestamp=%s",
                order,
                next_timestamp,
            )
            orders_row["timestamp"] = timestamp
            # Copy content of the order.
            orders_row.update(order.to_dict())
            # Get the current holding for the asset of the order.
            holdings = self.get_holdings_as_scalar(last_timestamp, order.asset_id)
            _LOG.debug("holdings=\n%s", hprint.dataframe_to_str(holdings))
            # Complete fills.
            orders_row["num_shares_filled"] = order.num_shares
            # TODO(gp): Allow partial fills.
            holdings += order.num_shares
            orders_row["holdings+1"] = holdings
            # Account for the executed price of the order.
            execution_price = order.get_execution_price()
            orders_row["execution_price"] = execution_price
            #
            cash -= execution_price * order.num_shares
            orders_row["cash+1"] = cash
            #
            # _LOG.debug("row=%s", row)
            orders_rows.append(orders_row)
            holdings_row = {
                "timestamp": next_timestamp,
                "asset_id": order.asset_id,
                "curr_num_shares": holdings,
            }
            holdings_rows.append(holdings_row)
        # Cash should not be negative after executing all the orders.
        hdbg.dassert_lte(0.0, cash, "cash=%s", cash)
        # Add the information to the orders.
        orders_tmp = self._concat(orders_rows, self._order_columns)
        self._orders = pd.concat([orders_tmp, self._orders])
        # Add the information to the holdings.
        holdings_tmp = self._concat(holdings_rows, self._holdings_columns)
        self._holdings = pd.concat([holdings_tmp, self._holdings])
        _LOG.debug(
            "after place_orders: orders=\n%s",
            hprint.dataframe_to_str(self._orders),
        )

    def get_pnl(self):
        """
        Return the time series of positions, PnL.
        """
        # strategyid                                  SAU1
        # tradedate                             2021-10-28
        # account                                SAU1_CAND
        # id                                         10005
        # cost_basis                                   0.0  ?
        # mark                                  795.946716  ?
        # avg_buy_px                                   0.0
        # avg_sell_px                                  0.0
        # qty_bought                                     0
        # qty_sold                                       0
        # quantity                                       0
        # position_pnl                                 0.0
        # trading_pnl                                  0.0
        # total_pnl                                    0.0
        # local_currency                               USD
        # portfolio_currency                           USD
        # fx                                           1.0
        # to_usd                                       1.0
        # timestamp_db          2021-10-28 20:40:05.517649
        return

    def get_bod_holdings(
        self, timestamp: pd.Timestamp, id_: Optional[Any]
    ) -> pd.DataFrame:
        """
        Return the holdings at the beginning of a day.
        """
        # tradedate       2021-10-28
        # id                   10005
        # strategyid            SAU1
        # account          SAU1_CAND
        # bod_position             0
        # bod_price              0.0
        # currency               USD
        # fx                     1.0
        # TODO(gp): Just implement from get_current_holdings.
        return

    @staticmethod
    def _concat(rows: List[Dict[str, Any]], columns: List[str]) -> pd.DataFrame:
        df_tmp = pd.DataFrame(rows)
        _LOG.debug("df_tmp=\n%s", hprint.dataframe_to_str(df_tmp))
        df_tmp.set_index("timestamp", drop=True, inplace=True)
        df_tmp.index.name = None
        df_tmp.sort_values("asset_id", inplace=True)
        hdbg.dassert_set_eq(df_tmp.columns, columns)
        return df_tmp
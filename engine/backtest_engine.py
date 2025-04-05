# engine/backtest_engine.py

import pandas as pd
import numpy as np

from utils.helpers import get_strike_price, get_nearest_option_price, get_next_weekly_expiry,get_timestamp


class BacktestEngine:
    """
    Backtests the given OptionStrategy over underlying equity data and computes PnL for option legs.
    Uses a data accessor to fetch option prices for each leg based on the underlying price at entry.
    """

    def __init__(self, underlying_data: pd.DataFrame, strategy, accessor, config: dict,
                 benchmark_data: pd.DataFrame = None):
        # Assume underlying_data is the full dataset covering a wide range of dates.
        # Create a trading calendar from the full dataset:
        self.trading_calendar = underlying_data.index.sort_values()  # full calendar

        # Now, filter the underlying data for trade iteration based on start and end dates:
        start_date = pd.to_datetime(config["backtest_settings"]["start_date"])
        end_date = pd.to_datetime(config["backtest_settings"]["end_date"])
        self.underlying_data = underlying_data.loc[
            (underlying_data.index >= start_date) & (underlying_data.index <= end_date)
            ]
        self.strategy = strategy
        self.accessor = accessor
        self.config = config
        self.benchmark_data = benchmark_data
        self.trades = []  # List of trade records
        self.equity_curve = []  # List of dicts with 'date' and 'equity'
        self.initial_capital = float(config["backtest_settings"].get("capital", 100000))
        self.contract_multiplier = config["underlying_asset"].get("multiplier", 50)
        self.lot_size = config["underlying_asset"].get("lot_size", 75)

    def run_backtest(self):
        capital = self.initial_capital
        in_position = False
        trade_context = {}  # To store entry data for the current trade

        # Get the allowed trading days from config. If not specified, assume all days.
        allowed_days = self.config["backtest_settings"].get("trading_days",["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])

        # Use self.trading_calendar (full set) for expiry logic.
        full_trading_dates = self.trading_calendar

        # Iterate over each timestamp in the underlying data
        for timestamp, row in self.underlying_data.iterrows():
            current_data = row.copy()
            current_data.name = timestamp

            # Check if today's day_name is in the allowed list
            day_name = timestamp.day_name()
            if day_name not in allowed_days:
                # Option A: Skip this day entirely (no entry logic, but still record equity)
                self.equity_curve.append({"date": timestamp, "equity": capital})
                continue

            if in_position:
                # Check exit conditions using underlying data row
                context = {
                    "entry_underlying_price": trade_context["entry_underlying_price"],
                    # "entry_capital": trade_context["entry_capital"],
                    "current_capital": capital,  # current account capital updated after previous trades
                    "option_data_series": trade_context["option_data_series"],
                    "entry_option_prices": trade_context["entry_option_prices"],
                    "legs": self.strategy.option_legs,
                    "contract_multiplier": self.contract_multiplier
                }
                exit_signal = any(cond.evaluate(current_data, self.underlying_data.loc[:timestamp], context)
                                  for cond in self.strategy.exit_conditions)
                if exit_signal:
                    total_profit = 0
                    legs_details = []
                    for leg_idx, leg in enumerate(self.strategy.option_legs):
                        option_df = trade_context["option_data_series"][leg_idx]
                        exit_option_price = get_nearest_option_price(option_df, timestamp)
                        entry_option_price = trade_context["entry_option_prices"][leg_idx]
                        lots = leg.quantity
                        if leg.action == "buy":
                            profit = (exit_option_price - entry_option_price) * self.lot_size * lots
                        else:
                            profit = (entry_option_price - exit_option_price) * self.lot_size * lots
                        total_profit += profit

                        # Log details for each leg
                        leg_detail = {
                            "leg_type": leg.option_type,
                            "action": leg.action,
                            "strike": leg.computed_strike,
                            "entry_option_price": entry_option_price,
                            "exit_option_price": exit_option_price,
                            "pnl": profit
                        }
                        legs_details.append(leg_detail)

                    trade = {
                        "entry_date": trade_context["entry_time"],
                        "exit_date": timestamp,
                        "entry_underlying_price": trade_context["entry_underlying_price"],
                        "exit_underlying_price": current_data["Price"],
                        "profit": total_profit,
                        "legs": legs_details  # Breakdown of each leg's details.
                    }
                    self.trades.append(trade)
                    capital += total_profit
                    in_position = False
                    trade_context = {}
            else:
                context = {}
                entry_signal = all(cond.evaluate(current_data, self.underlying_data.loc[:timestamp], context)
                                   for cond in self.strategy.entry_conditions)
                if entry_signal:
                    trade_context["entry_time"] = timestamp
                    trade_context["entry_underlying_price"] = current_data["Price"]
                    option_data_series = []
                    entry_option_prices = []
                    underlying_symbol = self.config["underlying_asset"]["symbol"]
                    # Determine expiry_date: If option_expiry is WEEKLY, compute expiry using the trading dates.
                    option_expiry_type = self.config["underlying_asset"].get("option_expiry", "").upper()
                    if option_expiry_type == "WEEKLY":
                        expiry_day = self.config["underlying_asset"].get("expiry_day", "THU") # Fallback : if expiry_day not found then THU is default
                        expiry_date = get_next_weekly_expiry(timestamp, expiry_day, full_trading_dates)
                    else:
                        expiry_date = self.config["backtest_settings"].get("expiry_date", "")
                    for leg in self.strategy.option_legs:
                        multiplier = self.config["underlying_asset"].get("multiplier", 50)
                        strike = get_strike_price(leg, current_data["Price"], multiplier)
                        leg.computed_strike = strike
                        try:
                            option_df = self.accessor.get_contract_prices(
                                underlying_symbol,
                                leg.option_type.upper(),
                                strike,
                                get_timestamp(expiry_date)
                            )
                        except Exception as e:
                            print(f"Error fetching option data for symbol {underlying_symbol} and {leg.option_type} {leg.action} strike {strike} expiry {expiry_date} date {timestamp}: {e}")
                            option_df = pd.DataFrame()
                        if not option_df.empty:
                            option_df["DateTime"] = pd.to_datetime(option_df["DateTime"], unit='s', utc=True).dt.tz_convert('Asia/Kolkata').dt.tz_localize(None)
                            option_df = option_df.drop_duplicates(subset="DateTime").sort_values("DateTime")
                            option_df["Close"] = option_df["Close"].fillna(method="ffill")
                        option_data_series.append(option_df)
                        if not option_df.empty:
                            entry_price = get_nearest_option_price(option_df, timestamp)
                        else:
                            entry_price = np.nan
                        entry_option_prices.append(entry_price)
                    trade_context["option_data_series"] = option_data_series
                    trade_context["entry_option_prices"] = entry_option_prices
                    in_position = True

            if in_position:
                current_equity = capital  # Unrealized PnL not marked-to-market in this demo
            else:
                current_equity = capital
            self.equity_curve.append({"date": timestamp, "equity": current_equity})

        self.equity_curve = pd.DataFrame(self.equity_curve).set_index("date")
        return self.trades

    def performance_metrics(self):
        trades_df = pd.DataFrame(self.trades)
        win_rate = (trades_df["profit"] > 0).mean() if not trades_df.empty else None
        self.equity_curve["returns"] = self.equity_curve["equity"].pct_change().fillna(0)
        if self.equity_curve["returns"].std() != 0:
            sharpe_ratio = np.sqrt(252) * self.equity_curve["returns"].mean() / self.equity_curve["returns"].std()
        else:
            sharpe_ratio = None
        return {"win_rate": win_rate, "sharpe_ratio": sharpe_ratio}

    def plot_results(self, return_fig=False):
        import matplotlib.pyplot as plt
        import pandas as pd
        import matplotlib.dates as mdates

        # ==========================
        # 1. Convert Intraday to Daily
        # ==========================

        # -- Equity Curve: group by date, take last record
        equity_df = self.equity_curve.copy()
        # Normalize index to remove the time component
        equity_df.index = equity_df.index.normalize()
        # Aggregate intraday points to daily last
        equity_df = equity_df.groupby(equity_df.index).last()

        # If a benchmark is present, do the same
        bench_df = None
        if self.benchmark_data is not None and not self.benchmark_data.empty:
            bench_df = self.benchmark_data.copy()
            bench_df.index = bench_df.index.normalize()
            bench_df = bench_df.groupby(bench_df.index).last()

        # If underlying_data is available, also aggregate it
        under_df = None
        if hasattr(self, "underlying_data") and "Price" in self.underlying_data.columns:
            under_df = self.underlying_data.copy()
            under_df.index = under_df.index.normalize()
            under_df = under_df.groupby(under_df.index).last()

        # ==========================
        # 2. Compute Performance Metrics and Data
        # ==========================
        metrics = self.performance_metrics()
        win_rate = metrics.get("win_rate", 0)
        sharpe = metrics.get("sharpe_ratio", 0)

        initial_capital = self.initial_capital
        equity_series = equity_df["equity"]

        # Strategy cumulative returns
        cum_returns_strategy = (equity_series / initial_capital) - 1

        # Benchmark cumulative returns
        cum_returns_bench = None
        if bench_df is not None:
            bench_prices = bench_df["Price"]
            bench_initial = bench_prices.iloc[0]
            cum_returns_bench = (bench_prices / bench_initial) - 1

        # Underlying cumulative returns
        cum_returns_under = None
        if under_df is not None:
            under_prices = under_df["Price"]
            under_initial = under_prices.iloc[0]
            cum_returns_under = (under_prices / under_initial) - 1

        # Compute drawdown for strategy
        running_max = equity_series.cummax()
        drawdown = (equity_series - running_max) / running_max
        max_drawdown = drawdown.min()

        # ==========================
        # 3. Aggregate trades by exit day (still daily-based, since we care about the date)
        # ==========================
        trades_df = None
        if len(self.trades) > 0:
            trades_df = pd.DataFrame(self.trades)
            trades_df["exit_date"] = pd.to_datetime(trades_df["exit_date"]).dt.normalize()
            trades_df["exit_day"] = trades_df["exit_date"].dt.day_name()
            day_profit = trades_df.groupby("exit_day")["profit"].agg(["mean", "count"])
            day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            day_profit = day_profit.reindex(day_order).fillna(0)

        # ==========================
        # 4. Plot the Results (Daily Frequency)
        # ==========================
        fig, axs = plt.subplots(2, 2, figsize=(16, 12))

        # --- Panel 1: Equity Curve ---
        axs[0, 0].plot(equity_series.index, equity_series, label="Strategy Equity", color='blue')
        if bench_df is not None:
            axs[0, 0].plot(bench_df.index, bench_df["Price"], label="Benchmark Price", color='orange')
        axs[0, 0].set_title("Equity Curve (Daily)")
        axs[0, 0].set_xlabel("Date")
        axs[0, 0].set_ylabel("Equity / Price")
        axs[0, 0].grid(True)
        axs[0, 0].legend()

        # Annotate key metrics
        axs[0, 0].text(
            0.02, 0.95,
            f"Win Rate: {win_rate:.2%}\nSharpe Ratio: {sharpe:.2f}\nMax Drawdown: {max_drawdown:.2%}",
            transform=axs[0, 0].transAxes,
            fontsize=10,
            verticalalignment='top',
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5)
        )

        # --- Panel 2: Cumulative Returns ---
        axs[0, 1].plot(cum_returns_strategy.index, cum_returns_strategy, label="Strategy Cumulative Return",
                       color='blue')
        if cum_returns_bench is not None:
            axs[0, 1].plot(cum_returns_bench.index, cum_returns_bench, label="Benchmark Cumulative Return",
                           color='orange')
        if cum_returns_under is not None:
            axs[0, 1].plot(cum_returns_under.index, cum_returns_under, label="Underlying Cumulative Return",
                           color='green')
        axs[0, 1].set_title("Cumulative Returns (Daily)")
        axs[0, 1].set_xlabel("Date")
        axs[0, 1].set_ylabel("Cumulative Return")
        axs[0, 1].grid(True)
        axs[0, 1].legend()

        # --- Panel 3: Drawdown (Strategy) ---
        axs[1, 0].plot(drawdown.index, drawdown, label="Drawdown", color='red')
        axs[1, 0].set_title("Drawdown (Daily)")
        axs[1, 0].set_xlabel("Date")
        axs[1, 0].set_ylabel("Drawdown (%)")
        axs[1, 0].grid(True)
        axs[1, 0].legend()

        # --- Panel 4: Average Profit by Exit Day ---
        if trades_df is not None:
            axs[1, 1].bar(day_profit.index, day_profit["mean"], color="green", alpha=0.7)
            axs[1, 1].set_title("Average Profit by Exit Day")
            axs[1, 1].set_xlabel("Day of Week")
            axs[1, 1].set_ylabel("Average Profit")
            axs[1, 1].grid(True, axis="y")
            # Annotate each bar with the count of trades on that day
            for idx, (day, row) in enumerate(day_profit.iterrows()):
                axs[1, 1].text(idx, row["mean"], f'{int(row["count"])}', ha='center', va='bottom', fontsize=9)
        else:
            axs[1, 1].text(
                0.5, 0.5,
                "No trades available for day-wise analysis",
                horizontalalignment='center',
                verticalalignment='center'
            )

        # Use a date formatter to clean up x-axis
        for i in range(2):
            for j in range(2):
                ax = axs[i, j]
                ax.xaxis.set_major_locator(mdates.AutoDateLocator())
                ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
                for label in ax.get_xticklabels():
                    label.set_rotation(45)
                    label.set_horizontalalignment('right')

        plt.tight_layout(pad=3.0)
        if return_fig:
            return fig
        else:
            plt.show()
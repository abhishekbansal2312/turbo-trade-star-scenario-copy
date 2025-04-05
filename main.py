# main.py

import os
import pandas as pd
from config.config_parser import get_strategy_config, update_underlying_asset_config
from utils.data_cleaning import clean_underlying_data
from engine.backtest_engine import BacktestEngine
from strategies.strategy import OptionStrategy, OptionLeg
from conditions.time_conditions import EntryTimeCondition, EntryDateCondition
from conditions.technical_conditions import MovingAverageCondition, StopLossCondition, VIXCondition, \
    TakeProfitCondition, TrailingStoplossCondition
# Import your data access layer (using your existing panda.py)
from data.panda import PandaAccessor
from data.constants import OPTION_DB_PATH, OUTPUT_PATH


def create_strategy_from_config(config: dict) -> OptionStrategy:
    strategy = OptionStrategy("User Configured Strategy")
    # Process legs
    for leg_conf in config.get("legs", []):
        leg = OptionLeg(
            option_type=leg_conf["type"],
            action=leg_conf["action"],
            strike_selection=leg_conf.get("strike_selection", {}),
            quantity=leg_conf.get("lots", 1)
        )
        strategy.add_option_leg(leg)

    # Process entry conditions
    entry_conf = config.get("entry_conditions", {})
    if "time" in entry_conf:
        strategy.add_entry_condition(EntryTimeCondition(entry_conf["time"]))
    if "date" in entry_conf:
        strategy.add_entry_condition(EntryDateCondition(entry_conf["date"]))
    if "indicator" in entry_conf:
        ind = entry_conf["indicator"]
        if "sma_crossover" in ind:
            strategy.add_entry_condition(MovingAverageCondition(window=ind["sma_crossover"], direction="above"))
    if "volatility" in entry_conf:
        vol = entry_conf["volatility"]
        if "vix_below" in vol:
            strategy.add_entry_condition(VIXCondition(threshold=vol["vix_below"], direction="below"))

    # Process exit conditions
    exit_conf = config.get("exit_conditions", {})
    if "time_exit" in exit_conf:
        strategy.add_exit_condition(EntryTimeCondition(exit_conf["time_exit"]))
    if "stoploss" in exit_conf:
        sl = exit_conf["stoploss"]
        if "%" in sl:
            pct = float(sl.replace("%", "")) / 100.0
            strategy.add_exit_condition(StopLossCondition(stoploss_pct=pct))
        else:
            strategy.add_exit_condition(StopLossCondition(stoploss_abs=float(sl)))
    if "take_profit" in exit_conf:
        tp = exit_conf["take_profit"]
        if "%" in tp:
            tp_pct = float(tp.replace("%", "")) / 100.0
            strategy.add_exit_condition(TakeProfitCondition(take_profit_pct=tp_pct))
        else:
            strategy.add_exit_condition(TakeProfitCondition(take_profit_abs=float(tp)))
    if "trailing_stoploss" in exit_conf:
        tsl = exit_conf["trailing_stoploss"]
        if "%" in tsl:
            tsl_pct = float(tsl.replace("%", "")) / 100.0
            strategy.add_exit_condition(TrailingStoplossCondition(trailing_stoploss_pct=tsl_pct))
    if "indicator_exit" in exit_conf:
        ind_exit = exit_conf["indicator_exit"]
        if "price_below_sma" in ind_exit:
            strategy.add_exit_condition(MovingAverageCondition(window=ind_exit["price_below_sma"], direction="below"))
    if "volatility_exit" in exit_conf:
        vol_exit = exit_conf["volatility_exit"]
        if "vix_above" in vol_exit:
            strategy.add_exit_condition(VIXCondition(threshold=vol_exit["vix_above"], direction="above"))

    return strategy


def main():
    accessor = PandaAccessor(OPTION_DB_PATH)

    config = get_strategy_config()
    config = update_underlying_asset_config(config)
    bs = config["backtest_settings"]
    symbol = config["underlying_asset"]["symbol"]
    start_date = bs["start_date"]
    end_date = bs["end_date"]

    try:
        #TODO: Fetch underlying data from your data source
        # read_file = "./data/stocks/" + symbol+'.csv'
        underlying_df = accessor.get_equity_data(symbol)
        underlying_df = underlying_df.rename(columns={'timestamp': 'DateTime', 'price': 'Price', 'symbol': 'Symbol'})
        underlying_df["DateTime"] = pd.to_datetime(underlying_df["DateTime"], unit='s', utc=True).dt.tz_convert('Asia/Kolkata').dt.tz_localize(None)
        # underlying_df = underlying_df[underlying_df['DateTime'].between(start_date, end_date)]
        # underlying_df['Symbol'] = symbol
        # underlying_df = accessor._query(
        #     """
        #     SELECT Symbol, DateTime, Price
        #     FROM EquityTick
        #     WHERE Symbol = ? AND DateTime BETWEEN ? AND ?
        #     ORDER BY DateTime;
        #     """,
        #     params=(symbol, start_date, end_date)
        # )
    except Exception as e:
        print(f"Error fetching underlying data: {e}")
        return

    if underlying_df.empty:
        print("No underlying data fetched.")
        return

    underlying_df = clean_underlying_data(underlying_df, time_col="DateTime", price_col="Price")

    # (Optional) Fetch benchmark data similarly if available.
    benchmark_df = None

    strategy = create_strategy_from_config(config)

    engine = BacktestEngine(underlying_df, strategy, accessor, config, benchmark_data=benchmark_df)
    trades = engine.run_backtest()
    metrics = engine.performance_metrics()

    print("Performance Metrics:", metrics)
    print("Trades executed:")
    for t in trades:
        print(t)

    engine.plot_results()

    log_conf = config.get("logging", {})
    if log_conf.get("save_results", False):
        output_path = OUTPUT_PATH
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        engine.equity_curve.to_csv(os.path.join(output_path, "equity_curve.csv"))
        trades_df = pd.DataFrame(trades)
        trades_df.to_csv(os.path.join(output_path, "trades.csv"), index=False)


if __name__ == "__main__":
    main()

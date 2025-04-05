# config/config_parser.py

strategy_config = {
    "underlying_asset": {
        "symbol": "BANKNIFTY",
        "option_expiry": "WEEKLY",
        "expiry_day": "THU",
        "atm_source": "FUTURES",
        "exchange": "NSE",
        "currency": "INR",
        "lot_size": 75,
        "multiplier": 50
    },
    "legs": [
        {"type": "CE", "action": "BUY", "strike_selection": {"method": "ATM"}, "lots": 2},
        {"type": "PE", "action": "SELL", "strike_selection": {"method": "offset", "value": "+200 pts"}, "lots": 1},
        {"type": "CE", "action": "SELL", "strike_selection": {"method": "delta", "value": 0.4}, "lots": 3}
    ],
    "entry_conditions": {
        "time": "9:45",
        # "date": "Friday",
        # "indicator": {"sma_crossover": 50, "rsi_below": 30, "macd_signal": True, "bollinger_breakout": {"window": 20, "std": 2}},
        # "volatility": {"vix_below": 20},
        # "greeks": {"delta_above": 0.3},
        # "volume": {"min_volume": 100000}
    },
    "exit_conditions": {
        "time_exit": "14:45",
        # "stoploss": {
        #     "account_stop_loss_pct": "2%",
        #     "strategy_stop_loss_pct": "2%",
        #     "underlying_move_stop_pct": "2%",
        #     "absolute_stop_loss": "1000"  # rupees
        # },
        # "take_profit": "5%",
        # "trailing_stoploss": "1%",
        # "indicator_exit": {"price_below_sma": 50},
        # "volatility_exit": {"vix_above": 25}
    },
    "execution": {
        "order_type": "limit",
        "time_in_force": "GTC",
        "slippage": "0.1%",
        "margin": "use_available",
        "order_validity": "day"
    },
    "re_entry": {
        "max_retries": 3,
        "cooldown_minutes": 15,
        "re_entry_conditions": {"price_reversal": True}
    },
    "risk_management": {
        "skip_trade_if_insufficient_funds": True,
        "scale_lots_if_insufficient_funds": False,
        "risk_per_trade_pct": 0.02,
        "max_daily_loss_pct": 0.05,
        "max_drawdown_pct": 0.2
    },
    "backtest_settings": {
        "capital": "100000",
        "position_sizing": "fixed_lots",
        "commission": "₹20 per trade",
        "data_frequency": "intraday",
        "data_source": "local_csv",
        "start_date": "2022-05-30",
        "end_date": "2022-06-03",
        # "trading_days": ["Monday", "Tuesday", "Wednesday","Thursday"]
    },
    "logging": {
        "log_level": "INFO",
        "save_results": True,
    },
    "reporting": {
        "metrics": ["sharpe_ratio", "win_rate", "max_drawdown", "profit_factor"],
        "plot_styles": {"theme": "default"}
    }
}

def get_strategy_config():
    return strategy_config


# New function to update underlying asset config from a static mapping:
def update_underlying_asset_config(config):
    static_mapping = {
        "NIFTY": {
            "expiry_day": "THU",
            "lot_size": 75,
            "multiplier": 50
        },
        "BANKNIFTY": {
            "expiry_day": "THU",  # or "FRI" if that's your standard
            "lot_size": 25,
            "multiplier": 100
        }
        # Add more underlying symbols if needed.
    }
    symbol = config.get("underlying_asset", {}).get("symbol", "").upper()
    if symbol in static_mapping:
        mapping = static_mapping[symbol]
        config["underlying_asset"].update(mapping)
    return config
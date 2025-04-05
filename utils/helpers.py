# utils/helpers.py

import pandas as pd
from datetime import datetime, timedelta

DAY_MAP = {
    "MON": 0,
    "TUE": 1,
    "WED": 2,
    "THU": 3,
    "FRI": 4,
    "SAT": 5,
    "SUN": 6
}

def get_timestamp(date: str) -> int:
    return int(datetime.strptime(date, "%Y-%m-%d").timestamp())

def get_nearest_option_price(option_df: pd.DataFrame, timestamp: pd.Timestamp) -> float:
    option_df["DateTime"] = pd.to_datetime(option_df["DateTime"])
    diffs = (option_df["DateTime"] - timestamp).abs()
    idx = diffs.idxmin()
    return option_df.loc[idx, "Close"]

def get_strike_price(leg, underlying_price: float, multiplier: float = 50) -> float:
    """
    Computes the strike price based on the leg's strike_selection method using the provided multiplier.
      - ATM: rounds the underlying price to the nearest multiple of multiplier.
      - offset: adds the numeric offset from a string like "+200 pts" to the ATM strike.
      - delta: uses a placeholder adjustment by subtracting one multiplier.
    """
    method = leg.strike_selection.get("method", "").lower()
    if method == "atm":
        return round(underlying_price / multiplier) * multiplier
    elif method == "offset":
        val_str = leg.strike_selection.get("value", "0")
        num = float("".join(ch for ch in val_str if ch in "-0123456789."))
        return round(underlying_price / multiplier) * multiplier + num
    elif method == "delta":
        return round(underlying_price / multiplier) * multiplier - multiplier
    else:
        return round(underlying_price / multiplier) * multiplier

def fetch_option_data_for_leg(accessor, underlying_symbol: str, leg, expiry_date: str):
    strike = leg.computed_strike
    return accessor.get_contract_prices(underlying_symbol, leg.option_type.upper(), strike, expiry_date)


def get_next_weekly_expiry(entry_time: datetime, expiry_day_str: str, trading_dates: pd.DatetimeIndex) -> str:
    """
    Given an entry time, an expiry day (e.g. "THU" or "FRI"), and a sorted pd.DatetimeIndex of trading days,
    compute the next weekly expiry date. If the candidate expiry day is a holiday (i.e. no data for that day),
    decrement day-by-day until a trading day is found.

    Returns the expiry date as a string in "YYYY-MM-DD" format.
    """
    expiry_day_str = expiry_day_str.upper()
    target_day = DAY_MAP.get(expiry_day_str, 3)  # Default to Thursday if unknown
    current_day = entry_time.weekday()
    days_until_target = (target_day - current_day) % 7

    candidate_expiry = entry_time + timedelta(days=days_until_target)

    # Build a set of trading days (as date objects) from the underlying trading_dates
    trading_dates_set = {d.date() for d in trading_dates}

    # If the candidate expiry date is not in the trading days (i.e. holiday),
    # move backward one day at a time until you find a trading day.
    while candidate_expiry.date() not in trading_dates_set:
        candidate_expiry = candidate_expiry - timedelta(days=1)

    return candidate_expiry.strftime("%Y-%m-%d")

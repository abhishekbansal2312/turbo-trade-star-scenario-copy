# utils/data_cleaning.py

import pandas as pd

def clean_underlying_data(df: pd.DataFrame, time_col: str = "DateTime", price_col: str = "Price") -> pd.DataFrame:
    df[time_col] = pd.to_datetime(df[time_col])
    df = df.drop_duplicates(subset=time_col)
    df = df.sort_values(by=time_col)
    df = df.set_index(time_col)
    df[price_col] = df[price_col].ffill()

    return df
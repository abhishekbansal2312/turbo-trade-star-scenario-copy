from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import pandas as pd
from fastapi.middleware.cors import CORSMiddleware

# Import your backtesting modules. Adjust the import paths as needed.
from config.config_parser import update_underlying_asset_config
from data.constants import OPTION_DB_PATH
from main import create_strategy_from_config
from engine.backtest_engine import BacktestEngine
from data.panda import PandaAccessor
from utils.data_cleaning import clean_underlying_data

app = FastAPI(title="Turbo Trade Backtesting API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Turbo Trade Backtesting API!"}


# Define Pydantic models for configuration
class OptionLegModel(BaseModel):
    type: str
    action: str
    strike_selection: Dict[str, Any]
    lots: int


class BacktestConfigModel(BaseModel):
    underlying_asset: Dict[str, Any]
    legs: List[OptionLegModel]
    entry_conditions: Dict[str, Any]
    exit_conditions: Dict[str, Any]
    backtest_settings: Dict[str, Any]
    # You can add other keys as needed


# Safe serialization function for trades
def safe_serialize_trades(trades):
    serialized_trades = []
    
    # If no trades, return an empty list
    if not trades:
        return []
    
    for trade in trades:
        serialized_trade = {}
        for key, value in trade.items():
            # Handle datetime fields
            if key == 'DateTime' or key == 'entry_time' or key == 'exit_time':
                if value is None:
                    serialized_trade[key] = "2000-01-01T00:00:00"  # Default date if empty
                else:
                    # Try to convert to string, fallback to default if fails
                    try:
                        serialized_trade[key] = str(value)
                    except:
                        serialized_trade[key] = "2000-01-01T00:00:00"
            else:
                # For non-datetime fields, try regular serialization
                try:
                    # Use simple string conversion for any problematic objects
                    serialized_trade[key] = str(value) if not isinstance(value, (int, float, bool, str, type(None))) else value
                except:
                    serialized_trade[key] = None
        
        serialized_trades.append(serialized_trade)
    
    return serialized_trades


@app.post("/run_backtest")
def run_backtest(config: BacktestConfigModel):
    try:
        # Convert the Pydantic model to a dictionary
        config_dict = config.dict()
        config_dict = update_underlying_asset_config(config_dict)
        symbol = config_dict["underlying_asset"]["symbol"]

        # Create the strategy object from config
        strategy = create_strategy_from_config(config_dict)

        # --- Instantiate Data Accessor ---
        accessor = PandaAccessor(OPTION_DB_PATH)

        # --- Load underlying data ---
        try:
            underlying_df = accessor.get_equity_data(symbol)
            underlying_df = underlying_df.rename(columns={'timestamp': 'DateTime', 'price': 'Price', 'symbol': 'Symbol'})
            underlying_df["DateTime"] = pd.to_datetime(underlying_df["DateTime"], unit='s', utc=True).dt.tz_convert('Asia/Kolkata').dt.tz_localize(None)

            # Clean underlying data
            underlying_df = clean_underlying_data(underlying_df, time_col="DateTime", price_col="Price")
        except Exception as data_error:
            print(f"Data loading error: {str(data_error)}")
            # Return meaningful error instead of failing
            return {
                "metrics": {"error": "Failed to load underlying data"},
                "trades": []
            }

        # --- Run the backtest ---
        engine = BacktestEngine(underlying_df, strategy, accessor, config_dict)
        trades = engine.run_backtest()
        metrics = engine.performance_metrics()

        # Apply safe serialization for trades
        serialized_trades = safe_serialize_trades(trades)

        return {
            "metrics": metrics,
            "trades": serialized_trades
        }
    except Exception as e:
        # Log the error but still return a valid response
        print(f"Error in backtest: {str(e)}")
        return {
            "metrics": {"error": str(e)},
            "trades": []
        }
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import pandas as pd
from fastapi.middleware.cors import CORSMiddleware
import traceback
from datetime import datetime

# Import backtesting modules
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


def format_trade_data(trades):
    """Format trade data for API response, handling various data types safely."""
    if not trades:
        return []
    
    formatted_trades = []
    for i, trade in enumerate(trades):
        try:
            # Create a new dict for the formatted trade
            formatted_trade = {}
            
            # Process each field in the trade dictionary
            for key, value in trade.items():
                # Handle datetime fields
                if isinstance(value, pd.Timestamp) or isinstance(value, datetime):
                    formatted_trade[key] = value.isoformat()
                # Handle numpy or pandas numeric types
                elif hasattr(value, 'item') and callable(getattr(value, 'item')):
                    try:
                        formatted_trade[key] = value.item()  # Convert numpy/pandas types to Python native
                    except:
                        formatted_trade[key] = float(value) if pd.notna(value) else None
                # Handle other types that might need special formatting
                elif pd.isna(value):
                    formatted_trade[key] = None
                else:
                    formatted_trade[key] = value
            
            # Add trade_id if not present
            if 'trade_id' not in formatted_trade:
                formatted_trade['trade_id'] = i + 1
                
            formatted_trades.append(formatted_trade)
        except Exception as e:
            print(f"Error formatting trade {i}: {str(e)}")
            # Include a simplified version of the trade that at least has an ID
            formatted_trades.append({
                "trade_id": i + 1,
                "error": f"Could not format trade: {str(e)}"
            })
    
    return formatted_trades


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
            
            # Check if we got valid data
            if underlying_df is None or underlying_df.empty:
                return {
                    "metrics": {"error": f"No data available for symbol: {symbol}"},
                    "trades": []
                }
            
            # Standardize column names
            underlying_df = underlying_df.rename(columns={
                'timestamp': 'DateTime', 
                'price': 'Price', 
                'symbol': 'Symbol'
            })
            
            # Convert timestamp to datetime
            underlying_df["DateTime"] = pd.to_datetime(underlying_df["DateTime"], unit='s', utc=True)
            underlying_df["DateTime"] = underlying_df["DateTime"].dt.tz_convert('Asia/Kolkata').dt.tz_localize(None)

            # Clean underlying data
            underlying_df = clean_underlying_data(underlying_df, time_col="DateTime", price_col="Price")
            
            # Check if data cleaning resulted in empty dataframe
            if underlying_df.empty:
                return {
                    "metrics": {"error": "Data cleaning resulted in empty dataset"},
                    "trades": []
                }
                
        except Exception as data_error:
            print(f"Data loading error: {str(data_error)}")
            print(traceback.format_exc())
            return {
                "metrics": {"error": f"Failed to load underlying data: {str(data_error)}"},
                "trades": []
            }

        # Apply date filters from backtest settings
        start_date = config_dict["backtest_settings"].get("start_date")
        end_date = config_dict["backtest_settings"].get("end_date")
        
        if start_date:
            try:
                start_date = pd.to_datetime(start_date)
                underlying_df = underlying_df[underlying_df["DateTime"] >= start_date]
            except:
                print(f"Invalid start_date format: {start_date}")
                
        if end_date:
            try:
                end_date = pd.to_datetime(end_date)
                underlying_df = underlying_df[underlying_df["DateTime"] <= end_date]
            except:
                print(f"Invalid end_date format: {end_date}")
        
        # Check if filtered data is empty
        if underlying_df.empty:
            return {
                "metrics": {"error": "No data available for the selected date range"},
                "trades": []
            }

        # --- Run the backtest ---
        engine = BacktestEngine(underlying_df, strategy, accessor, config_dict)
        trades = engine.run_backtest()
        
        # Generate performance metrics
        try:
            metrics = engine.performance_metrics()
        except Exception as metrics_error:
            print(f"Error calculating metrics: {str(metrics_error)}")
            print(traceback.format_exc())
            # If metrics fail, provide a basic structure
            metrics = {
                "error": f"Failed to calculate performance metrics: {str(metrics_error)}",
                "symbol": symbol
            }

        # Format trades for API response
        formatted_trades = format_trade_data(trades)

        return {
            "metrics": metrics,
            "trades": formatted_trades
        }
    except Exception as e:
        # Log the full error with traceback
        print(f"Error in backtest: {str(e)}")
        print(traceback.format_exc())
        
        return {
            "metrics": {"error": str(e)},
            "trades": []
        }
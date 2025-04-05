from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import pandas as pd
from fastapi.middleware.cors import CORSMiddleware  # Import CORS middleware

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
        # Update the DB path accordingly
        accessor = PandaAccessor(OPTION_DB_PATH)

        # --- Load underlying data ---
        underlying_df = accessor.get_equity_data(symbol)
        underlying_df = underlying_df.rename(columns={'timestamp': 'DateTime', 'price': 'Price', 'symbol': 'Symbol'})
        underlying_df["DateTime"] = pd.to_datetime(underlying_df["DateTime"], unit='s', utc=True).dt.tz_convert('Asia/Kolkata').dt.tz_localize(None)

        # Clean underlying data
        underlying_df = clean_underlying_data(underlying_df, time_col="DateTime", price_col="Price")

        # --- Run the backtest ---
        engine = BacktestEngine(underlying_df, strategy, accessor, config_dict)
        trades = engine.run_backtest()
        metrics = engine.performance_metrics()

        # # --- Generate the plot ---
        # # Ensure your plot_results method returns a matplotlib figure when return_fig=True.
        # fig = engine.plot_results(return_fig=True)
        # buf = io.BytesIO()
        # fig.savefig(buf, format="png")
        # buf.seek(0)
        # img_base64 = base64.b64encode(buf.read()).decode("utf-8")

        return {
            "metrics": metrics,
            "trades": trades,
            # "plot": img_base64
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
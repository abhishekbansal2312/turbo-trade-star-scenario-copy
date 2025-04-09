from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import pandas as pd
from fastapi.middleware.cors import CORSMiddleware
import random
from datetime import datetime, timedelta

# Import only what we need
from config.config_parser import update_underlying_asset_config

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

@app.post("/run_backtest")
def run_backtest(config: BacktestConfigModel):
    try:
        # Extract config for generating simulated results
        config_dict = config.dict()
        config_dict = update_underlying_asset_config(config_dict)
        
        # Extract some parameters for simulation
        symbol = config_dict["underlying_asset"]["symbol"]
        start_date_str = config_dict["backtest_settings"].get("start_date", "2023-01-01")
        end_date_str = config_dict["backtest_settings"].get("end_date", "2023-12-31")
        
        # Convert dates for simulation
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        except:
            # Use defaults if date parsing fails
            start_date = datetime(2023, 1, 1)
            end_date = datetime(2023, 12, 31)
        
        # Generate simulated metrics
        simulated_metrics = {
            "total_return": round(random.uniform(5.0, 25.0), 2),
            "annualized_return": round(random.uniform(4.0, 20.0), 2),
            "sharpe_ratio": round(random.uniform(0.8, 2.5), 2),
            "max_drawdown": round(random.uniform(-20.0, -5.0), 2),
            "win_rate": round(random.uniform(50.0, 80.0), 2),
            "profit_factor": round(random.uniform(1.2, 2.5), 2),
            "symbol": symbol
        }
        
        # Generate simulated trades
        simulated_trades = []
        
        # Number of trades to generate
        num_trades = random.randint(5, 15)
        
        # Generate random trades between start and end dates
        current_date = start_date
        for i in range(num_trades):
            # Random entry date
            entry_date = current_date + timedelta(days=random.randint(1, 10))
            if entry_date > end_date:
                break
                
            # Random exit date after entry
            exit_date = entry_date + timedelta(days=random.randint(1, 7))
            if exit_date > end_date:
                exit_date = end_date
            
            # Generate random prices
            entry_price = round(random.uniform(100.0, 150.0), 2)
            
            # 70% chance of profit
            if random.random() < 0.7:
                exit_price = round(entry_price * (1 + random.uniform(0.01, 0.08)), 2)
            else:
                exit_price = round(entry_price * (1 - random.uniform(0.01, 0.05)), 2)
            
            # Calculate P&L
            pnl = round(exit_price - entry_price, 2)
            pnl_pct = round((pnl / entry_price) * 100, 2)
            
            # Create trade object - using string representation of dates to avoid serialization issues
            trade = {
                "trade_id": i + 1,
                "entry_date": entry_date.strftime("%Y-%m-%d"),
                "entry_time": entry_date.strftime("%H:%M:%S"),
                "entry_price": entry_price,
                "exit_date": exit_date.strftime("%Y-%m-%d"),
                "exit_time": exit_date.strftime("%H:%M:%S"),
                "exit_price": exit_price,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "option_type": config_dict["legs"][0]["type"] if config_dict["legs"] else "CE",
                "action": config_dict["legs"][0]["action"] if config_dict["legs"] else "BUY"
            }
            
            simulated_trades.append(trade)
            current_date = exit_date
        
        # Return simulated results
        return {
            "metrics": simulated_metrics,
            "trades": simulated_trades
        }
            
    except Exception as e:
        # Log the actual exception for debugging
        import traceback
        print(f"Error in run_backtest: {str(e)}")
        print(traceback.format_exc())
        
        # Return error but still with a valid structure
        return {
            "metrics": {"error": str(e)},
            "trades": []
        }
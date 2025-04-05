# app.py
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import os
# Import configuration, engine, and data access from your project package.
# Adjust the import paths as needed.
from config.config_parser import get_strategy_config, update_underlying_asset_config
from engine.backtest_engine import BacktestEngine
from data.panda import PandaAccessor
from utils.data_cleaning import clean_underlying_data
from main import create_strategy_from_config

# Set page config for better appearance
st.set_page_config(page_title="Backtesting Engine UI", layout="wide")

# ----- Custom CSS for a professional trading-platform look -----
st.markdown(
    """
    <style>
    .stApp {
         background-image: url("https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?ixlib=rb-4.0.3&auto=format&fit=crop&w=1950&q=80");
         background-size: cover;
         background-attachment: fixed;
    }
    .block-container {
         background-color: rgba(0, 0, 0, 0.7) !important;
         padding: 2rem;
         border-radius: 10px;
    }
    .stApp .main {
         background-color: rgba(0, 0, 0, 0.7) !important;
         padding: 2rem;
         border-radius: 10px;
    }
    .stMarkdown, .stText, .stLabel, .stSelectbox, .stNumberInput, .stMultiselect, .stTextInput {
         color: #FFFFFF;
    }
    h1, h2, h3, h4, h5, h6 {
         color: #FFFFFF;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Title and Intro
st.title("Backtesting Engine UI")
st.markdown("## TURBO TRADE")

# Sidebar: General Configuration Options
st.sidebar.header("General Configuration")

# ---------- Build Config Dictionary ----------
config = get_strategy_config()
config = update_underlying_asset_config(config)

# ---------- Underlying Asset Configuration ----------
underlying_symbol = st.sidebar.selectbox("Underlying Symbol", options=["NIFTY", "BANKNIFTY"], index=0)
option_expiry = st.sidebar.selectbox("Option Expiry", options=["WEEKLY", "MONTHLY"], index=0)
expiry_day = st.sidebar.text_input("Expiry Day", value=config['underlying_asset']['expiry_day'])
trading_days = st.sidebar.multiselect("Trading Days (for new entries)",
                                      options=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                                      default=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])

# ---------- Entry Conditions ----------
st.sidebar.header("Entry Conditions")
entry_time = st.sidebar.text_input("Entry Time", value="10:15")
# entry_day = st.sidebar.text_input("Entry Day (Keep blank if trade all day else put day name like Monday/Friday etc)", value="")
# sma_window_entry = st.sidebar.number_input("SMA Crossover Window (Entry)", value=50, step=1)
# vix_below_entry = st.sidebar.text_input("VIX Below (Entry)", value="20")

# ---------- Exit Conditions ----------
st.sidebar.header("Exit Conditions")
exit_time = st.sidebar.text_input("Exit Time", value="14:45")
# sma_window_exit = st.sidebar.number_input("SMA Below Window (Exit)", value=50, step=1)
# vix_above_exit = st.sidebar.text_input("VIX Above (Exit)", value="25")

# ---------- Strategy Parameters ----------
st.sidebar.header("Strategy Parameters")
# stoploss = st.sidebar.text_input("Stoploss", value="2%")
# take_profit = st.sidebar.text_input("Take Profit", value="5%")
# trailing_stoploss = st.sidebar.text_input("Trailing Stoploss", value="1%")

# ---------- Backtest Settings ----------
st.sidebar.header("Backtest Settings")
capital = st.sidebar.number_input("Capital", value=100000, step=1000)
start_date = st.sidebar.date_input("Start Date", value=datetime(2022, 8, 1))
end_date = st.sidebar.date_input("End Date", value=datetime(2022, 12, 30))

# ---------- Option Leg Configuration ----------
st.sidebar.header("Option Leg Configuration")

# Initialize session state for option legs if not already set
if "option_legs" not in st.session_state:
    st.session_state.option_legs = []

with st.sidebar.form(key="new_leg_form"):
    st.markdown('<h3 style="color: #1E90FF;">Add a New Option Leg</h3>', unsafe_allow_html=True)
    new_leg_type = st.selectbox("Option Leg Type", options=["CE", "PE"], key="leg_type")
    new_leg_action = st.selectbox("Option Leg Action", options=["BUY", "SELL"], key="leg_action")
    new_strike_method = st.selectbox("Strike Selection Method", options=["ATM", "offset", "delta"], key="strike_method")
    new_strike_value = st.text_input("Strike Selection Value (if applicable)", value="", key="strike_value")
    new_leg_lots = st.number_input("Lots", value=1, step=1, key="leg_lots")
    submitted = st.form_submit_button("Add Leg")
    if submitted:
        st.session_state.option_legs.append({
            "type": new_leg_type,
            "action": new_leg_action,
            "strike_selection": {"method": new_strike_method, "value": new_strike_value},
            "lots": new_leg_lots
        })
        st.success("Option leg added!")

# Display current option legs
st.sidebar.subheader("Current Option Legs")
st.sidebar.json(st.session_state.option_legs)

# Update underlying asset configuration
config["underlying_asset"]["symbol"] = underlying_symbol
config["underlying_asset"]["option_expiry"] = option_expiry
config["underlying_asset"]["expiry_day"] = expiry_day

# Update backtest settings
config["backtest_settings"]["capital"] = str(capital)
config["backtest_settings"]["start_date"] = start_date.strftime("%Y-%m-%d")
config["backtest_settings"]["end_date"] = end_date.strftime("%Y-%m-%d")
config["backtest_settings"]["trading_days"] = trading_days

# Update exit conditions with stoploss, take profit, trailing stoploss.
# config["exit_conditions"]["stoploss"] = stoploss
# config["exit_conditions"]["take_profit"] = take_profit
# config["exit_conditions"]["trailing_stoploss"] = trailing_stoploss

# Update option legs configuration with the dynamic list from session state.
if st.session_state.option_legs:
    config["legs"] = st.session_state.option_legs
else:
    # Fallback default if no legs have been added yet.
    config["legs"] = [{
        "type": "CE",
        "action": "BUY",
        "strike_selection": {"method": "ATM", "value": ""},
        "lots": 1
    }]

st.sidebar.subheader("Current Config")
st.sidebar.json(config)

# ---------- Run Backtest Button ----------
if st.sidebar.button("Run Backtest"):
    st.write("Running backtest with the following configuration:")
    st.json(config)

    # Instantiate the data accessor – update DB_PATH as necessary.
    # DB_PATH = os.path.join(os.getcwd(), "data", "sqlite", "options.db")
    accessor = PandaAccessor("/Users/prabhu/PycharmProjects/turbo-trade/data/sqlite/options.db")

    # Fetch underlying equity data.
    try:
        # For demonstration, reading a CSV file from disk.
        read_file = "/Users/prabhu/PycharmProjects/turbo-trade/new_backtest/" + underlying_symbol+'.csv'
        underlying_df = pd.read_csv(read_file)
        # Rename columns if necessary
        underlying_df = underlying_df.rename(columns={'Date/Time': 'DateTime', 'CLose': 'Price'})
        underlying_df['DateTime'] = pd.to_datetime(underlying_df['DateTime'])
        underlying_df['Symbol'] = underlying_symbol
    except Exception as e:
        st.error(f"Error fetching underlying data: {e}")
        underlying_df = None

    if underlying_df is None or underlying_df.empty:
        st.error("No underlying data found.")
    else:
        # Clean the underlying data
        underlying_df = clean_underlying_data(underlying_df, time_col="DateTime", price_col="Price")

        # Create the strategy from the updated config
        strategy = create_strategy_from_config(config)

        # Instantiate the backtest engine
        engine = BacktestEngine(underlying_df, strategy, accessor, config)

        # Run the backtest
        trades = engine.run_backtest()
        metrics = engine.performance_metrics()

        st.write("Performance Metrics:", metrics)
        st.write("Trades Executed:", trades)

        # Generate the plot (ensure plot_results accepts return_fig argument)
        fig = engine.plot_results(return_fig=True)
        st.pyplot(fig)
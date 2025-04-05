# NOTE: create separate files for separate accessors in future to avoid confusion

FETCH_CONTRACT_ID = """
    SELECT Id 
    FROM OptionsContract 
    WHERE ExpiryDate = ?
        AND Type = ?
        AND StrikePrice = ?
        AND Symbol = ?;
"""

FETCH_CONTRACT_PRICES = """
    SELECT DateTime, Open, High, Low, Close, Volume, OI 
    FROM OptionsTick 
    WHERE ContractId = ?
    ORDER BY DateTime;
"""

FETCH_CONTRACTS_BY_SYMBOL_AND_EXPIRY = """
    SELECT Id, ExpiryDate, Type, StrikePrice, Symbol
    FROM OptionsContract 
    WHERE Symbol = ? AND ExpiryDate = ?
    ORDER BY StrikePrice;
"""

FETCH_ALL_SYMBOLS = "SELECT * FROM Symbol;"

FETCH_EQUITY_PRICE_BY_DATE_RANGE = """
    SELECT Symbol, DateTime, Price
    FROM EquityTick
    WHERE Symbol = ? AND DateTime BETWEEN ? AND ?
    ORDER BY DateTime;
"""

FETCH_EQUITY_PRICE_BY_SYMBOL = """
    SELECT Symbol, DateTime, Price
    FROM EquityTick
    WHERE Symbol = ?
    ORDER BY DateTime;
"""

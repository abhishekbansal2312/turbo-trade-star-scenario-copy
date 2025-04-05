import sqlite3
import data.query as queries
from typing import Optional
import pandas

# TODO: make the code strongly typed, according to the need of the layer

class PandaAccessor:
    def __init__(self, db_path: str) -> None:
        self.__db_path = db_path
    def _query(self, query: str, params: Optional[tuple] = None) -> pandas.DataFrame:
        with sqlite3.connect(self.__db_path) as conn:
            df = pandas.read_sql_query(query, conn, params=params)  # type: ignore
    
        return df

    def get_contract_id(self, symbol, option_type, strike_price, expiry_date):
        result = self._query(queries.FETCH_CONTRACT_ID, (expiry_date, option_type, strike_price, symbol))
        try:
            contract_id = int(result.loc[0]["Id"]) # type: ignore
        except:
            contract_id = None
        return contract_id

    def get_contract_prices(self, symbol, option_type, strike_price, expiry_date):
        contract_id = self.get_contract_id(symbol, option_type, strike_price, expiry_date)
        if contract_id is None:
            raise ValueError("Contract not found for the given parameters.")

        return self._query(queries.FETCH_CONTRACT_PRICES, (contract_id,))

    def get_contract_by_symbol_and_expiry(self, symbol, expiry_date):
        return self._query(queries.FETCH_CONTRACTS_BY_SYMBOL_AND_EXPIRY, (symbol, expiry_date))

    def get_symbols(self):
        return self._query(queries.FETCH_ALL_SYMBOLS)
    
    def get_equity_data_by_date(self, symbol, start_date, end_date):
        return self._query(queries.FETCH_EQUITY_PRICE_BY_DATE_RANGE, (symbol, start_date, end_date))
    
    def get_equity_data(self, symbol):
        return self._query(queries.FETCH_EQUITY_PRICE_BY_SYMBOL, (symbol,))

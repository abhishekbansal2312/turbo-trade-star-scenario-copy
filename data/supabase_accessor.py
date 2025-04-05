# data/supabase_accessor.py
from supabase import create_client
import os
import pandas as pd

class SupabaseAccessor:
    def __init__(self):
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        self.supabase = create_client(url, key)
    
    def get_equity_data(self, symbol):
        response = self.supabase.table('equity_data').select('*').eq('symbol', symbol).execute()
        return pd.DataFrame(response.data)
    
    def get_option_data(self, symbol, expiry_date, strike, option_type):
        response = self.supabase.table('option_data') \
            .select('*') \
            .eq('symbol', symbol) \
            .eq('expiry_date', expiry_date) \
            .eq('strike', strike) \
            .eq('option_type', option_type) \
            .execute()
        return pd.DataFrame(response.data)
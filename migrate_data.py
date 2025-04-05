import sqlite3
import pandas as pd
from supabase import create_client
import os
import time
from tqdm import tqdm
import logging
import sys
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"migration_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Configuration
SQLITE_DB_PATH = './data/sample/options.db'
SUPABASE_URL = "https://dckmlrxrciltfgydpwld.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRja21scnhyY2lsdGZneWRwd2xkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDM2NjE5MDgsImV4cCI6MjA1OTIzNzkwOH0.9WP723A3P0FKRLVf3GPqGfyogu8wLRQE4J48ERmg8wU"
BATCH_SIZE = 1000
CHUNK_SIZE = 50000  # Number of rows to process at once for large tables

def connect_to_sqlite():
    """Establish connection to SQLite database with error handling"""
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        logger.info("Successfully connected to SQLite database")
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to SQLite database: {e}")
        sys.exit(1)

def connect_to_supabase():
    """Establish connection to Supabase with error handling"""
    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Successfully connected to Supabase")
        return supabase_client
    except Exception as e:
        logger.error(f"Failed to connect to Supabase: {e}")
        sys.exit(1)

def get_table_info(conn, table_name):
    """Get column information for a table"""
    cursor = conn.cursor()
    try:
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = cursor.fetchall()
        logger.info(f"{table_name} columns: {[col[1] for col in columns]}")
        return [col[1] for col in columns]
    except Exception as e:
        logger.error(f"Failed to get table info for {table_name}: {e}")
        return []

def get_row_count(conn, table_name):
    """Get the number of rows in a table"""
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        logger.info(f"Table {table_name} contains {count} rows")
        return count
    except Exception as e:
        logger.error(f"Failed to get row count for {table_name}: {e}")
        return 0

def extract_equity_data(conn):
    """Extract equity data from SQLite database"""
    try:
        logger.info("Extracting equity data...")
        equity_query = """
        SELECT Symbol as symbol, DateTime as timestamp, Price as price
        FROM EquityTick
        """
        equity_data = pd.read_sql(equity_query, conn)
        equity_data['timestamp'] = pd.to_datetime(equity_data['timestamp'], unit='s')
        logger.info(f"Extracted {len(equity_data)} equity data records")
        return equity_data
    except Exception as e:
        logger.error(f"Failed to extract equity data: {e}")
        return pd.DataFrame()

def extract_contract_data(conn):
    """Extract options contract data from SQLite database"""
    try:
        logger.info("Extracting options contract data...")
        contract_query = """
        SELECT * FROM OptionsContract
        """
        contract_data = pd.read_sql(contract_query, conn)
        logger.info(f"Retrieved {len(contract_data)} options contracts")
        return contract_data
    except Exception as e:
        logger.error(f"Failed to extract contract data: {e}")
        return pd.DataFrame()

def extract_options_tick_data(conn, total_rows):
    """Extract options tick data in chunks to handle large datasets"""
    try:
        logger.info("Extracting options tick data in chunks...")
        
        # Initialize an empty DataFrame to store all chunks
        all_options_data = pd.DataFrame()
        
        # Calculate how many chunks we need
        num_chunks = (total_rows // CHUNK_SIZE) + 1
        
        for chunk in tqdm(range(num_chunks), desc="Processing chunks"):
            offset = chunk * CHUNK_SIZE
            chunk_query = f"""
            SELECT * FROM OptionsTick
            LIMIT {CHUNK_SIZE} OFFSET {offset}
            """
            chunk_data = pd.read_sql(chunk_query, conn)
            
            if chunk_data.empty:
                break
                
            all_options_data = pd.concat([all_options_data, chunk_data])
            
        logger.info(f"Retrieved {len(all_options_data)} options ticks")
        return all_options_data
    except Exception as e:
        logger.error(f"Failed to extract options tick data: {e}")
        return pd.DataFrame()

def process_options_data(options_tick_data, contract_data):
    """Process and join options data"""
    try:
        logger.info("Processing and joining options data...")
        # Merge the datasets based on ContractId
        merged_options = options_tick_data.merge(
            contract_data, 
            left_on='ContractId', 
            right_on='Id',
            how='left'
        )
        
        # Check for any null values after merge
        null_count = merged_options['Symbol'].isnull().sum()
        if null_count > 0:
            logger.warning(f"Found {null_count} records with missing symbol after merge")
        
        # Convert to target schema
        option_data = pd.DataFrame({
            'symbol': merged_options['Symbol'],
            'expiry_date': pd.to_datetime(merged_options['ExpiryDate']),
            'strike': merged_options['StrikePrice'],
            'option_type': merged_options['Type'],
            'timestamp': pd.to_datetime(merged_options['DateTime'], unit='s'),
            'price': merged_options['Close'],
        })
        
        # Drop rows with null values
        option_data = option_data.dropna()
        
        logger.info(f"Processed {len(option_data)} option data records")
        return option_data
    except Exception as e:
        logger.error(f"Failed to process options data: {e}")
        return pd.DataFrame()

def upload_to_supabase(supabase, table_name, data):
    """Upload data to Supabase in batches with error handling and retries"""
    if data.empty:
        logger.warning(f"No data to upload to {table_name}")
        return False
    
    logger.info(f"Uploading data to {table_name}...")
    total_batches = (len(data) // BATCH_SIZE) + 1
    
    # Convert timestamps to ISO format strings that are JSON serializable
    data_copy = data.copy()
    for col in data_copy.select_dtypes(include=['datetime64[ns]']).columns:
        data_copy[col] = data_copy[col].dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
    
    for i in tqdm(range(0, len(data_copy), BATCH_SIZE), desc=f"Uploading to {table_name}"):
        batch = data_copy.iloc[i:i+BATCH_SIZE].to_dict(orient='records')
        batch_num = i // BATCH_SIZE + 1
        
        # Try up to 3 times for each batch
        max_retries = 3
        for attempt in range(max_retries):
            try:
                supabase.table(table_name).insert(batch).execute()
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Upload failed for batch {batch_num}/{total_batches}. Retrying ({attempt+1}/{max_retries})... Error: {e}")
                    time.sleep(2)  # Wait before retrying
                else:
                    logger.error(f"Failed to upload batch {batch_num}/{total_batches} after {max_retries} attempts: {e}")
                    return False
    
    logger.info(f"Successfully uploaded all data to {table_name}")
    return True

def main():
    start_time = time.time()
    logger.info("Starting data migration process")
    
    # Connect to databases
    sqlite_conn = connect_to_sqlite()
    supabase = connect_to_supabase()
    
    try:
        # Get table information
        get_table_info(sqlite_conn, "OptionsTick")
        get_table_info(sqlite_conn, "OptionsContract")
        
        # Get row counts for large tables
        options_tick_count = get_row_count(sqlite_conn, "OptionsTick")
        
        # Extract data
        equity_data = extract_equity_data(sqlite_conn)
        contract_data = extract_contract_data(sqlite_conn)
        options_tick_data = extract_options_tick_data(sqlite_conn, options_tick_count)
        
        # Process options data
        option_data = process_options_data(options_tick_data, contract_data)
        
        # Close SQLite connection after extracting all data
        sqlite_conn.close()
        logger.info("SQLite data extraction completed and connection closed")
        
        # Upload data to Supabase
        equity_success = upload_to_supabase(supabase, 'equity_data', equity_data)
        option_success = upload_to_supabase(supabase, 'option_data', option_data)
        
        if equity_success and option_success:
            logger.info("Data migration completed successfully!")
        else:
            logger.warning("Data migration completed with some issues. Check the logs for details.")
        
        elapsed_time = time.time() - start_time
        logger.info(f"Total migration time: {elapsed_time:.2f} seconds")
        
    except Exception as e:
        logger.error(f"An unexpected error occurred during migration: {e}")
    finally:
        # Ensure connections are closed
        if 'sqlite_conn' in locals() and sqlite_conn:
            sqlite_conn.close()
            
if __name__ == "__main__":
    main()
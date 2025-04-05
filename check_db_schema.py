import sqlite3

# SQLite database path
SQLITE_DB_PATH = './data/sqlite/options.db'

# Connect to SQLite database
conn = sqlite3.connect(SQLITE_DB_PATH)
cursor = conn.cursor()

# Check tables in database
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tables in database:", [table[0] for table in tables])

# Check EquityTick table structure
print("\nEquityTick table columns:")
try:
    cursor.execute("PRAGMA table_info(EquityTick);")
    columns = cursor.fetchall()
    for col in columns:
        print(f"Column: {col[1]}, Type: {col[2]}")
except Exception as e:
    print(f"Error checking EquityTick structure: {e}")

# Check OptionTick table structure
print("\nOptionTick table columns:")
try:
    cursor.execute("PRAGMA table_info(OptionTick);")
    columns = cursor.fetchall()
    for col in columns:
        print(f"Column: {col[1]}, Type: {col[2]}")
except Exception as e:
    print(f"Error checking OptionTick structure: {e}")

conn.close()
import mysql.connector
from mysql.connector import Error

# Replace with your actual credentials
DB_CONFIG = {
    'user': 'sql12772919',
    'password': '2AJ7HJjAcQ',
    'host': 'sql12.freesqldatabase.com',
    'database': 'sql12772919',
    'port': 3306
}

try:
    conn = mysql.connector.connect(**DB_CONFIG)
    if conn.is_connected():
        print("✅ Successfully connected to the database.")
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES;")
        tables = cursor.fetchall()
        print("📦 Tables in the database:")
        for table in tables:
            print(f" - {table[0]}")
    else:
        print("❌ Failed to connect to the database.")
except Error as e:
    print(f"❗ Error: {e}")
finally:
    if 'conn' in locals() and conn.is_connected():
        conn.close()
        print("🔌 Connection closed.")

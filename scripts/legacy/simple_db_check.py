import sqlite3
import os

db_path = 'football.db'
if not os.path.exists(db_path):
    print(f"Error: {db_path} not found.")
else:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        print("Querying games...")
        cursor.execute("SELECT id, status, date_time FROM games ORDER BY id DESC LIMIT 10")
        rows = cursor.fetchall()
        for row in rows:
            print(row)
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

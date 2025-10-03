import sqlite3

conn = sqlite3.connect("targets.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS targets (
    chat_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    lang TEXT
)
""")

conn.commit()
conn.close()

print("✅ دیتابیس targets.db ساخته شد.")

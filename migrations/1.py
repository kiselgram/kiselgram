# add_avatar_columns.py
import sqlite3

conn = sqlite3.connect('../instance/kiselgram.db')
cursor = conn.cursor()

# Add avatar_url to groups
try:
    cursor.execute("ALTER TABLE groups ADD COLUMN avatar_url VARCHAR(500)")
    print("Added avatar_url to groups table")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e):
        print("avatar_url already exists in groups")
    else:
        print(f"Error: {e}")

# Add avatar_url to channels
try:
    cursor.execute("ALTER TABLE channels ADD COLUMN avatar_url VARCHAR(500)")
    print("Added avatar_url to channels table")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e):
        print("avatar_url already exists in channels")
    else:
        print(f"Error: {e}")

conn.commit()
conn.close()
print("Database update complete!")
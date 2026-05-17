# migrate_custom.py – Safe custom migration for Kiselgram merge
# Run anytime: python migrate_custom.py

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'kiselgram.db')

def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())

def table_exists(cursor, table):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cursor.fetchone() is not None

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    print("🔧 Starting migration…")

    # --------- new tables ---------
    # pinned_chats
    if not table_exists(cursor, 'pinned_chats'):
        cursor.execute('''
            CREATE TABLE pinned_chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_type VARCHAR(20) NOT NULL,
                chat_id INTEGER NOT NULL,
                pinned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES user(id),
                UNIQUE(user_id, chat_type, chat_id)
            )
        ''')
        print("✅ Created table: pinned_chats")
    else:
        print("⏭️  Table pinned_chats already exists")

    # email_verifications
    if not table_exists(cursor, 'email_verifications'):
        cursor.execute('''
            CREATE TABLE email_verifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token VARCHAR(100) UNIQUE NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME NOT NULL,
                verified BOOLEAN DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES user(id)
            )
        ''')
        print("✅ Created table: email_verifications")
    else:
        print("⏭️  Table email_verifications already exists")

    # -------- missing table: user_session --------
    if not table_exists(cursor, 'user_session'):
        cursor.execute('''
            CREATE TABLE user_session (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_token VARCHAR(255) UNIQUE NOT NULL,
                device VARCHAR(200),
                ip_address VARCHAR(45),
                user_agent VARCHAR(500),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_activity DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY(user_id) REFERENCES user(id)
            )
        ''')
        print("✅ Created table: user_session (with all columns)")
    else:
        # user_session exists, just make sure it has the 'device' column
        if not column_exists(cursor, 'user_session', 'device'):
            cursor.execute("ALTER TABLE user_session ADD COLUMN device VARCHAR(200)")
            print("✅ Added column user_session.device")
        else:
            print("⏭️  Column user_session.device already exists")

    # -------- extra column on user --------
    if not column_exists(cursor, 'user', 'email_verified'):
        cursor.execute("ALTER TABLE user ADD COLUMN email_verified BOOLEAN DEFAULT 0")
        print("✅ Added column user.email_verified")
    else:
        print("⏭️  Column user.email_verified already exists")

    conn.commit()
    conn.close()
    print("🎉 Migration completed successfully.")

if __name__ == '__main__':
    migrate()
"""Migration to add push subscriptions, encryption, premium, and profile fields."""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
import os

# Create a minimal app to access the database
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.getcwd(), 'instance', 'kiselgram.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

def upgrade():
    with app.app_context():
        # PushSubscription table
        db.session.execute(text('''
            CREATE TABLE IF NOT EXISTS push_subscription (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                endpoint TEXT NOT NULL,
                p256dh TEXT NOT NULL,
                auth TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES user (id)
            )
        '''))

        # Add columns to message table (ignore errors if column exists)
        columns_to_add = [
            ('is_encrypted', 'BOOLEAN DEFAULT FALSE'),
            ('encrypted_content', 'TEXT'),
            ('encryption_key_id', 'INTEGER')
        ]
        for col_name, col_def in columns_to_add:
            try:
                db.session.execute(text(f'ALTER TABLE message ADD COLUMN {col_name} {col_def}'))
            except Exception as e:
                print(f"Column {col_name} may already exist: {e}")

        # Add columns to user table
        user_columns = [
            ('profile_completed', 'BOOLEAN DEFAULT FALSE'),
            ('is_admin', 'BOOLEAN DEFAULT FALSE'),
            ('is_premium', 'BOOLEAN DEFAULT FALSE'),
            ('premium_since', 'TIMESTAMP'),
            ('premium_expires_at', 'TIMESTAMP')
        ]
        for col_name, col_def in user_columns:
            try:
                db.session.execute(text(f'ALTER TABLE user ADD COLUMN {col_name} {col_def}'))
            except Exception as e:
                print(f"Column {col_name} may already exist: {e}")

        db.session.commit()
        print("✅ Migration completed successfully.")

if __name__ == '__main__':
    upgrade()
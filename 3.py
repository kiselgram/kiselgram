# migrations/add_premium_feature_fields.py
"""Add premium feature fields to User table"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from sqlalchemy import text


def upgrade():
    """Add premium fields to User table"""
    app = create_app()

    with app.app_context():
        # Ensure instance folder exists
        instance_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance')
        os.makedirs(instance_path, exist_ok=True)

        # Create tables if they don't exist
        db.create_all()

        with db.engine.connect() as conn:
            # Check existing columns
            inspector = db.inspect(db.engine)
            existing_columns = [c['name'] for c in inspector.get_columns('user')]

            columns_to_add = [
                ('is_premium', 'BOOLEAN DEFAULT FALSE'),
                ('premium_since', 'DATETIME'),
                ('premium_expires_at', 'DATETIME'),
                ('premium_auto_renew', 'BOOLEAN DEFAULT FALSE'),
                ('premium_plan', 'VARCHAR(20)'),
                ('avatar_type', 'VARCHAR(10) DEFAULT "image"'),
                ('notification_sound', 'VARCHAR(50) DEFAULT "default"'),
                ('per_chat_sounds', 'JSON'),
                ('mute_all', 'BOOLEAN DEFAULT FALSE'),
                ('do_not_disturb', 'BOOLEAN DEFAULT FALSE'),
                ('is_bot', 'BOOLEAN DEFAULT FALSE'),
                ('bot_owner_id', 'INTEGER'),
                ('bot_token', 'VARCHAR(64)'),
                ('is_admin', 'BOOLEAN DEFAULT FALSE'),
            ]

            for col_name, col_type in columns_to_add:
                if col_name not in existing_columns:
                    try:
                        print(f"Adding column: {col_name}")
                        conn.execute(text(f"ALTER TABLE user ADD COLUMN {col_name} {col_type}"))
                        conn.commit()
                        print(f"  ✅ Added {col_name}")
                    except Exception as e:
                        print(f"  ⚠️ Could not add {col_name}: {e}")
                else:
                    print(f"  ✓ {col_name} already exists")

            print("\n✅ Premium feature fields migration complete!")


def downgrade():
    """Remove premium fields (SQLite doesn't support DROP COLUMN easily)"""
    print("⚠️ SQLite doesn't support DROP COLUMN.")
    print("To downgrade, you need to:")
    print("1. Create a backup of your database")
    print("2. Create a new table without premium fields")
    print("3. Copy data over")
    print("4. Drop old table and rename new one")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--downgrade', action='store_true', help='Run downgrade')
    args = parser.parse_args()

    if args.downgrade:
        downgrade()
    else:
        upgrade()
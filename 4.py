# check_config.py
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app

app = create_app()
with app.app_context():
    print(f"Database URI: {app.config.get('SQLALCHEMY_DATABASE_URI')}")
    print(f"Instance path: {app.instance_path}")

    # Check if directory exists
    db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if db_uri.startswith('sqlite:///'):
        db_path = db_uri.replace('sqlite:///', '')
        print(f"Database path: {db_path}")
        print(f"Directory exists: {os.path.exists(os.path.dirname(db_path) if os.path.dirname(db_path) else '.')}")
        print(f"File exists: {os.path.exists(db_path)}")
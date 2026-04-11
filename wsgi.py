#!/usr/bin/env python3
"""
WSGI entry point for Kiselgram production deployment.
Run with: gunicorn wsgi:app
"""

import os
import sys

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app

# Create the application instance
app = create_app()

if __name__ == "__main__":
    app.run()
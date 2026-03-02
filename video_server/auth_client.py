import requests
from functools import wraps
from flask import request, jsonify, session
import os

class KiselgramAuthClient:
    """Client to authenticate with main Kiselgram server"""

    def __init__(self, main_server_url="http://localhost:5000"):
        self.main_server_url = main_server_url

    def verify_session(self, session_data):
        """Verify session with main server"""
        try:
            response = requests.post(
                f"{self.main_server_url}/api/verify-session",
                json=session_data,
                timeout=2
            )
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return None

    def get_user_info(self, user_id):
        """Get user info from main server"""
        try:
            response = requests.get(
                f"{self.main_server_url}/api/user/{user_id}",
                timeout=2
            )
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return None

# Create global auth client
auth_client = KiselgramAuthClient()

def login_required_video(f):
    """Decorator to check login via main Kiselgram server"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user is logged in via session
        user_id = request.headers.get('X-User-ID')
        username = request.headers.get('X-Username')

        if not user_id or not username:
            return jsonify({'error': 'Not authenticated'}), 401

        # Verify with main server (optional - can be cached)
        # For now, trust the headers from main server
        return f(user_id, username, *args, **kwargs)

    return decorated_function

from flask import Blueprint, render_template, jsonify, redirect, url_for, session, request as flask_request
import requests
import os
import dotenv
import logging
from urllib.parse import quote
from functools import wraps

# Set up logging
logger = logging.getLogger(__name__)

video_int_bp = Blueprint('video', __name__, url_prefix='/video')

dotenv.load_dotenv()

# Configuration
VIDEO_HOST = os.environ.get('VIDEO_HOST', 'localhost')
VIDEO_PORT = os.environ.get('VIDEO_PORT', '5001')
VIDEO_BASE_URL = f"http://{VIDEO_HOST}:{VIDEO_PORT}"
VIDEO_TIMEOUT = 5  # seconds


def get_video_url():
    """Get the base URL for the video server"""
    return VIDEO_BASE_URL


def check_video_server():
    """Check if video server is running"""
    try:
        response = requests.get(f"{VIDEO_BASE_URL}/health", timeout=VIDEO_TIMEOUT)
        return response.status_code == 200
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return False


def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if flask_request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'Not authenticated', 'login_required': True}), 401
            return redirect(url_for('auth.login', next=flask_request.url))
        return f(*args, **kwargs)
    return decorated_function


def video_server_required(f):
    """Decorator to check if video server is running"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not check_video_server():
            if flask_request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'Video server not running'}), 503
            return render_template('video_server_down.html'), 503
        return f(*args, **kwargs)
    return decorated_function


@video_int_bp.route('/')
@login_required
@video_server_required
def video_index():
    """Video chat landing page"""
    try:
        # Get active rooms to display
        rooms_response = requests.get(f"{VIDEO_BASE_URL}/rooms", timeout=VIDEO_TIMEOUT)
        rooms = rooms_response.json() if rooms_response.status_code == 200 else []
    except:
        rooms = []

    return render_template('video_integration.html',
                         username=session.get('username'),
                         user_id=session.get('user_id'),
                         rooms=rooms,
                         video_server_url=VIDEO_BASE_URL)


@video_int_bp.route('/create-room', methods=['POST'])
@login_required
@video_server_required
def create_room():
    """Create a video room on the video server"""
    try:
        # Get room name from request if provided
        data = flask_request.get_json(silent=True) or {}
        room_name = data.get('room_name', f"{session.get('username')}'s Room")

        response = requests.post(
            f"{VIDEO_BASE_URL}/rooms/create",
            json={
                'username': session.get('username'),
                'user_id': session.get('user_id'),
                'room_name': room_name,
                'created_by': session.get('user_id')
            },
            timeout=VIDEO_TIMEOUT
        )

        if response.status_code == 200:
            logger.info(f"Room created by {session.get('username')}")
            return response.json()
        else:
            return jsonify({'error': 'Failed to create room', 'details': response.text}), response.status_code

    except requests.exceptions.ConnectionError:
        logger.error("Video server connection failed")
        return jsonify({'error': 'Video server not running'}), 503
    except requests.exceptions.Timeout:
        logger.error("Video server timeout")
        return jsonify({'error': 'Video server timeout'}), 504
    except Exception as e:
        logger.error(f"Error creating room: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@video_int_bp.route('/rooms')
@login_required
@video_server_required
def list_rooms():
    """List active video rooms"""
    try:
        response = requests.get(f"{VIDEO_BASE_URL}/rooms", timeout=VIDEO_TIMEOUT)

        if response.status_code == 200:
            rooms = response.json()
            return jsonify(rooms)
        else:
            return jsonify({'error': 'Failed to fetch rooms'}), response.status_code

    except requests.exceptions.ConnectionError:
        logger.error("Video server connection failed")
        return jsonify({'error': 'Video server not running'}), 503
    except requests.exceptions.Timeout:
        logger.error("Video server timeout")
        return jsonify({'error': 'Video server timeout'}), 504


@video_int_bp.route('/room/<room_id>')
@login_required
@video_server_required
def join_room(room_id):
    """Redirect to video room with auth"""
    # URL encode the username to handle special characters
    encoded_username = quote(session.get('username', ''))

    redirect_url = (
        f"{VIDEO_BASE_URL}/room/{room_id}"
        f"?username={encoded_username}"
        f"&user_id={session.get('user_id')}"
    )

    logger.info(f"User {session.get('username')} joining room {room_id}")
    return redirect(redirect_url)


@video_int_bp.route('/room/<room_id>/info')
@login_required
@video_server_required
def room_info(room_id):
    """Get information about a specific room"""
    try:
        response = requests.get(
            f"{VIDEO_BASE_URL}/rooms/{room_id}",
            timeout=VIDEO_TIMEOUT
        )

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return jsonify({'error': 'Room not found'}), 404
        else:
            return jsonify({'error': 'Failed to fetch room info'}), response.status_code

    except requests.exceptions.ConnectionError:
        return jsonify({'error': 'Video server not running'}), 503
    except requests.exceptions.Timeout:
        return jsonify({'error': 'Video server timeout'}), 504


@video_int_bp.route('/health')
def health_check():
    """Check if video server is accessible"""
    if check_video_server():
        return jsonify({
            'status': 'ok',
            'video_server': 'running',
            'url': VIDEO_BASE_URL
        })
    else:
        return jsonify({
            'status': 'degraded',
            'video_server': 'down',
            'url': VIDEO_BASE_URL
        }), 503


@video_int_bp.route('/leave/<room_id>', methods=['POST'])
@login_required
def leave_room(room_id):
    """Notify video server that user left a room"""
    try:
        response = requests.post(
            f"{VIDEO_BASE_URL}/rooms/{room_id}/leave",
            json={'user_id': session.get('user_id')},
            timeout=VIDEO_TIMEOUT
        )
        return jsonify({'success': True})
    except:
        # Even if video server doesn't respond, we consider the user left
        return jsonify({'success': True})
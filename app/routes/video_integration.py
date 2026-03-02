from flask import Blueprint, render_template, jsonify, redirect, url_for, session
import requests

video_int_bp = Blueprint('video_int', __name__, url_prefix='/video')

VIDEO_SERVER_URL = "http://localhost:5001"

@video_int_bp.route('/')
def video_index():
    """Video chat landing page"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    return render_template('video_integration.html',
                         username=session.get('username'),
                         user_id=session.get('user_id'))

@video_int_bp.route('/create-room')
def create_room():
    """Create a video room on the video server"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    try:
        response = requests.post(
            f"{VIDEO_SERVER_URL}/api/rooms/create",
            json={
                'username': session.get('username'),
                'user_id': session.get('user_id')
            }
        )
        return response.json()
    except requests.exceptions.ConnectionError:
        return jsonify({'error': 'Video server not running'}), 503

@video_int_bp.route('/rooms')
def list_rooms():
    """List active video rooms"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    try:
        response = requests.get(f"{VIDEO_SERVER_URL}/api/rooms")
        return response.json()
    except requests.exceptions.ConnectionError:
        return jsonify({'error': 'Video server not running'}), 503

@video_int_bp.route('/join/<room_id>')
def join_room(room_id):
    """Redirect to video room with auth"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    return redirect(
        f"{VIDEO_SERVER_URL}/room/{room_id}?username={session.get('username')}&user_id={session.get('user_id')}"
    )

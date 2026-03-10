from flask import Flask, render_template, jsonify, request, send_from_directory, abort
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
from datetime import datetime, timedelta
import uuid
import os
import json
import logging
import threading
import time

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__,
            static_folder='static',
            template_folder='templates')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24).hex())
app.config['PORT'] = int(os.environ.get('VIDEO_PORT', 5001))
app.config['HOST'] = os.environ.get('VIDEO_HOST', '0.0.0.0')
app.config['MAX_ROOM_AGE'] = 3600  # 1 hour in seconds
app.config['CLEANUP_INTERVAL'] = 300  # 5 minutes

# Enable CORS for main server
CORS(app, origins=["http://localhost:5000", "http://127.0.0.1:5000"])

socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60, ping_interval=25)

# Store active video rooms and participants
video_rooms = {}
active_users = {}
room_creation_times = {}


# Background cleanup thread
def cleanup_old_rooms():
    """Remove inactive rooms periodically"""
    while True:
        time.sleep(app.config['CLEANUP_INTERVAL'])
        current_time = datetime.utcnow()
        rooms_to_remove = []

        for room_id, room_data in video_rooms.items():
            created_at = datetime.fromisoformat(room_data['created_at'])
            age = (current_time - created_at).total_seconds()

            # Remove rooms older than MAX_ROOM_AGE with no participants
            if age > app.config['MAX_ROOM_AGE'] and len(active_users.get(room_id, {})) == 0:
                rooms_to_remove.append(room_id)

        for room_id in rooms_to_remove:
            del video_rooms[room_id]
            if room_id in active_users:
                del active_users[room_id]
            if room_id in room_creation_times:
                del room_creation_times[room_id]
            logger.info(f"Cleaned up inactive room: {room_id}")


# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_old_rooms, daemon=True)
cleanup_thread.start()


@app.route('/')
def index():
    """Root endpoint with server info"""
    return jsonify({
        'service': 'Kiselgram Video Server',
        'status': 'running',
        'version': '2.0',
        'port': app.config['PORT'],
        'host': app.config['HOST'],
        'active_rooms': len(video_rooms),
        'active_participants': sum(len(users) for users in active_users.values()),
        'endpoints': {
            'health': '/api/health',
            'rooms': '/api/rooms',
            'room_detail': '/api/rooms/<room_id>',
            'create_room': '/api/rooms/create',
            'join_room': '/room/<room_id>',
            'websocket': 'SocketIO on same port'
        }
    })


@app.route('/api/health')
@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'uptime': 'N/A',  # Could track actual uptime
        'active_rooms': len(video_rooms),
        'active_participants': sum(len(users) for users in active_users.values())
    })


@app.route('/api/rooms')
def list_rooms():
    """List all active video rooms"""
    rooms_list = []
    for room_id, room_data in video_rooms.items():
        if room_data.get('active', True):
            participant_count = len(active_users.get(room_id, {}))
            rooms_list.append({
                'room_id': room_id,
                'room_name': room_data.get('room_name', f"Room {room_id}"),
                'created_by': room_data['created_by_username'],
                'created_by_id': room_data['created_by'],
                'created_at': room_data['created_at'],
                'participants': participant_count,
                'max_participants': room_data.get('max_participants', 10),
                'has_video': participant_count > 0
            })

    # Sort by creation time (newest first)
    rooms_list.sort(key=lambda x: x['created_at'], reverse=True)

    return jsonify({
        'success': True,
        'count': len(rooms_list),
        'rooms': rooms_list
    })


@app.route('/api/rooms/create', methods=['POST'])
def create_room():
    """Create a new video room"""
    data = request.get_json() or {}
    username = data.get('username', 'Anonymous')
    user_id = data.get('user_id', str(uuid.uuid4()))
    room_name = data.get('room_name', f"{username}'s Room")
    max_participants = min(int(data.get('max_participants', 10)), 50)  # Cap at 50

    # Generate unique room ID
    room_id = str(uuid.uuid4())[:8]
    while room_id in video_rooms:  # Ensure uniqueness
        room_id = str(uuid.uuid4())[:8]

    video_rooms[room_id] = {
        'created_by': user_id,
        'created_by_username': username,
        'created_at': datetime.utcnow().isoformat(),
        'room_name': room_name,
        'active': True,
        'max_participants': max_participants,
        'settings': {
            'allow_screenshare': data.get('allow_screenshare', True),
            'allow_chat': data.get('allow_chat', True),
            'require_permission': data.get('require_permission', False)
        }
    }

    room_creation_times[room_id] = time.time()
    logger.info(f"Room created: {room_id} by {username}")

    return jsonify({
        'success': True,
        'room_id': room_id,
        'room_name': room_name,
        'join_url': f"http://localhost:{app.config['PORT']}/room/{room_id}"
    })


@app.route('/api/rooms/<room_id>')
def get_room(room_id):
    """Get room information"""
    if room_id not in video_rooms:
        return jsonify({'error': 'Room not found'}), 404

    room = video_rooms[room_id]
    participant_count = len(active_users.get(room_id, {}))

    # Get participant list (without socket IDs for privacy)
    participants = []
    if room_id in active_users:
        participants = [{
            'username': user['username'],
            'user_id': user['user_id'],
            'joined_at': user.get('joined_at', 'unknown'),
            'audio_only': user.get('audio_only', False),
            'screensharing': user.get('screensharing', False)
        } for user in active_users[room_id].values()]

    return jsonify({
        'success': True,
        'room': {
            'room_id': room_id,
            'room_name': room.get('room_name', f"Room {room_id}"),
            'created_by': room['created_by_username'],
            'created_by_id': room['created_by'],
            'created_at': room['created_at'],
            'active': room.get('active', True),
            'participants': participant_count,
            'participant_list': participants,
            'max_participants': room.get('max_participants', 10),
            'settings': room.get('settings', {})
        }
    })


@app.route('/api/rooms/<room_id>/delete', methods=['POST'])
def delete_room(room_id):
    """Delete a room (only creator can delete)"""
    if room_id not in video_rooms:
        return jsonify({'error': 'Room not found'}), 404

    data = request.get_json() or {}
    user_id = data.get('user_id')

    # Verify user is room creator
    if video_rooms[room_id]['created_by'] != user_id:
        return jsonify({'error': 'Only room creator can delete room'}), 403

    # Notify all participants
    socketio.emit('room-closed', {
        'room_id': room_id,
        'message': 'Room has been closed by creator'
    }, room=f"video_{room_id}")

    # Remove room data
    del video_rooms[room_id]
    if room_id in active_users:
        del active_users[room_id]
    if room_id in room_creation_times:
        del room_creation_times[room_id]

    logger.info(f"Room deleted: {room_id}")
    return jsonify({'success': True, 'message': 'Room deleted'})


@app.route('/room/<room_id>')
def video_room(room_id):
    """Video chat room page"""
    if room_id not in video_rooms:
        return render_template('video/room_not_found.html', room_id=room_id), 404

    # Get user info from query params (passed from main server)
    username = request.args.get('username', 'Anonymous')
    user_id = request.args.get('user_id', '0')

    # Check if room is full
    current_participants = len(active_users.get(room_id, {}))
    max_participants = video_rooms[room_id].get('max_participants', 10)

    if current_participants >= max_participants:
        return render_template('video/room_full.html',
                               room_id=room_id,
                               max_participants=max_participants), 403

    return render_template('video/room.html',
                           room_id=room_id,
                           username=username,
                           user_id=user_id,
                           room_name=video_rooms[room_id].get('room_name', f"Room {room_id}"),
                           server_port=app.config['PORT'],
                           server_host=app.config['HOST'],
                           created_by=video_rooms[room_id]['created_by_username'],
                           max_participants=max_participants)


@app.route('/static/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory('static', path)


# SocketIO Events
@socketio.on('join')
def handle_join(data):
    """Handle user joining video room"""
    room_id = data['room']
    username = data.get('username', 'Anonymous')
    user_id = data.get('user_id', '0')
    audio_only = data.get('audio_only', False)

    # Check if room exists
    if room_id not in video_rooms:
        emit('error', {'message': 'Room does not exist'})
        return

    room_name = f"video_{room_id}"
    join_room(room_name)

    # Store user info
    if room_id not in active_users:
        active_users[room_id] = {}

    active_users[room_id][request.sid] = {
        'username': username,
        'user_id': user_id,
        'sid': request.sid,
        'audio_only': audio_only,
        'screensharing': False,
        'joined_at': datetime.utcnow().isoformat()
    }

    logger.info(f"User {username} joined room {room_id}")

    # Notify others
    emit('user-joined', {
        'username': username,
        'user_id': user_id,
        'sid': request.sid,
        'audio_only': audio_only
    }, room=room_name, include_self=False)

    # Send existing users list
    existing_users = [{
        'username': user['username'],
        'user_id': user['user_id'],
        'sid': sid,
        'audio_only': user.get('audio_only', False),
        'screensharing': user.get('screensharing', False)
    } for sid, user in active_users[room_id].items() if sid != request.sid]

    emit('existing-users', {'users': existing_users}, room=request.sid)

    # Send room info
    emit('room-info', {
        'room_id': room_id,
        'room_name': video_rooms[room_id].get('room_name'),
        'created_by': video_rooms[room_id]['created_by_username'],
        'participant_count': len(active_users[room_id])
    }, room=request.sid)


@socketio.on('offer')
def handle_offer(data):
    """Handle WebRTC offer"""
    emit('offer', {
        'offer': data['offer'],
        'from': request.sid,
        'from_username': data.get('from_username', 'Unknown')
    }, room=data['to'])


@socketio.on('answer')
def handle_answer(data):
    """Handle WebRTC answer"""
    emit('answer', {
        'answer': data['answer'],
        'from': request.sid,
        'from_username': data.get('from_username', 'Unknown')
    }, room=data['to'])


@socketio.on('ice-candidate')
def handle_ice_candidate(data):
    """Handle ICE candidate"""
    emit('ice-candidate', {
        'candidate': data['candidate'],
        'from': request.sid
    }, room=data['to'])


@socketio.on('start-screenshare')
def handle_start_screenshare(data):
    """Handle screenshare start"""
    room_id = data['room']

    if room_id in active_users and request.sid in active_users[room_id]:
        active_users[room_id][request.sid]['screensharing'] = True

        emit('screenshare-started', {
            'sid': request.sid,
            'username': active_users[room_id][request.sid]['username']
        }, room=f"video_{room_id}", include_self=False)


@socketio.on('stop-screenshare')
def handle_stop_screenshare(data):
    """Handle screenshare stop"""
    room_id = data['room']

    if room_id in active_users and request.sid in active_users[room_id]:
        active_users[room_id][request.sid]['screensharing'] = False

        emit('screenshare-stopped', {
            'sid': request.sid
        }, room=f"video_{room_id}", include_self=False)


@socketio.on('switch-camera')
def handle_switch_camera(data):
    """Handle camera switch"""
    room_id = data['room']
    emit('camera-switched', {
        'from': request.sid,
        'device_id': data.get('device_id'),
        'device_label': data.get('device_label', 'Camera')
    }, room=f"video_{room_id}", include_self=False)


@socketio.on('toggle-audio')
def handle_toggle_audio(data):
    """Handle audio mute/unmute"""
    room_id = data['room']
    muted = data.get('muted', True)

    emit('audio-toggled', {
        'sid': request.sid,
        'muted': muted
    }, room=f"video_{room_id}", include_self=False)


@socketio.on('toggle-video')
def handle_toggle_video(data):
    """Handle video on/off"""
    room_id = data['room']
    enabled = data.get('enabled', True)

    emit('video-toggled', {
        'sid': request.sid,
        'enabled': enabled
    }, room=f"video_{room_id}", include_self=False)


@socketio.on('toggle-audio-only')
def handle_toggle_audio_only(data):
    """Handle audio-only mode toggle"""
    room_id = data['room']
    audio_only = data['audio_only']

    if room_id in active_users and request.sid in active_users[room_id]:
        active_users[room_id][request.sid]['audio_only'] = audio_only

        emit('user-mode-changed', {
            'sid': request.sid,
            'audio_only': audio_only
        }, room=f"video_{room_id}", include_self=False)


@socketio.on('chat-message')
def handle_chat_message(data):
    """Handle chat messages in video room"""
    room_id = data['room']
    message = data['message']
    username = data.get('username', 'Anonymous')

    emit('new-chat-message', {
        'username': username,
        'message': message,
        'timestamp': datetime.utcnow().isoformat(),
        'sid': request.sid
    }, room=f"video_{room_id}")


@socketio.on('get-participants')
def handle_get_participants(data):
    """Get list of participants in a room"""
    room_id = data['room']

    if room_id in active_users:
        participants = [{
            'username': user['username'],
            'user_id': user['user_id'],
            'sid': sid,
            'audio_only': user.get('audio_only', False),
            'screensharing': user.get('screensharing', False)
        } for sid, user in active_users[room_id].items()]

        emit('participants-list', {'participants': participants}, room=request.sid)


@socketio.on('raise-hand')
def handle_raise_hand(data):
    """Handle raise hand feature"""
    room_id = data['room']

    if room_id in active_users and request.sid in active_users[room_id]:
        username = active_users[room_id][request.sid]['username']

        emit('hand-raised', {
            'username': username,
            'sid': request.sid
        }, room=f"video_{room_id}")


@socketio.on('leave')
def handle_leave(data):
    """Handle user leaving video room"""
    room_id = data['room']
    room_name = f"video_{room_id}"
    leave_room(room_name)

    if room_id in active_users and request.sid in active_users[room_id]:
        user_data = active_users[room_id][request.sid]
        username = user_data['username']
        user_id = user_data['user_id']

        del active_users[room_id][request.sid]

        logger.info(f"User {username} left room {room_id}")

        emit('user-left', {
            'username': username,
            'user_id': user_id,
            'sid': request.sid
        }, room=room_name)

        # If room becomes empty, optionally keep it for a while
        if len(active_users.get(room_id, {})) == 0:
            logger.info(f"Room {room_id} is now empty")


@socketio.on('disconnect')
def handle_disconnect():
    """Handle socket disconnection"""
    for room_id in list(active_users.keys()):
        if request.sid in active_users[room_id]:
            user_data = active_users[room_id][request.sid]
            username = user_data['username']
            user_id = user_data['user_id']

            del active_users[room_id][request.sid]

            emit('user-left', {
                'username': username,
                'user_id': user_id,
                'sid': request.sid
            }, room=f"video_{room_id}")

            logger.info(f"User {username} disconnected from room {room_id}")
            break


# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500


def run():
    """Main function to start the server"""
    print(f"🎥 Video server starting...")
    print(f"   Port: {app.config['PORT']}")
    print(f"   Host: {app.config['HOST']}")
    print(f"   WebSocket: enabled")
    print(f"   CORS: enabled for http://localhost:5000")
    print(f"   Room cleanup interval: {app.config['CLEANUP_INTERVAL']}s")
    print(f"   Max room age: {app.config['MAX_ROOM_AGE']}s")
    print("-" * 40)
    print(f"📡 API endpoint: http://{app.config['HOST']}:{app.config['PORT']}/")
    print(f"🔌 WebSocket: ws://{app.config['HOST']}:{app.config['PORT']}")
    print(f"📊 Health check: http://{app.config['HOST']}:{app.config['PORT']}/health")
    print("=" * 40)

    socketio.run(app,
                 debug=True,
                 port=app.config['PORT'],
                 host=app.config['HOST'])


if __name__ == '__main__':
    run()
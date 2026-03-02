from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
from datetime import datetime
import uuid
import os
import json


app = Flask(__name__,
            static_folder='static',
            template_folder='templates')
app.config['SECRET_KEY'] = os.urandom(24).hex()
app.config['PORT'] = 5001

# Enable CORS for main server
CORS(app, origins=["http://localhost:5000"])

socketio = SocketIO(app, cors_allowed_origins="*")

# Store active video rooms and participants
video_rooms = {}
active_users = {}

@app.route('/')
def index():
    return jsonify({
        'service': 'Kiselgram Video Server',
        'status': 'running',
        'port': 5001,
        'endpoints': {
            'health': '/health',
            'rooms': '/api/rooms',
            'create_room': '/api/rooms/create',
            'websocket': 'SocketIO on same port'
        }
    })

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'active_rooms': len(video_rooms),
        'active_participants': sum(len(users) for users in active_users.values())
    })

@app.route('/api/rooms')
def list_rooms():
    """List all active video rooms"""
    rooms_list = []
    for room_id, room_data in video_rooms.items():
        if room_data.get('active', True):
            rooms_list.append({
                'room_id': room_id,
                'created_by': room_data['created_by_username'],
                'created_at': room_data['created_at'],
                'participants': len(active_users.get(room_id, {}))
            })

    return jsonify({
        'success': True,
        'rooms': rooms_list
    })

@app.route('/api/rooms/create', methods=['POST'])
def create_room():
    """Create a new video room"""
    data = request.get_json() or {}
    username = data.get('username', 'Anonymous')
    user_id = data.get('user_id', '0')

    room_id = str(uuid.uuid4())[:8]

    video_rooms[room_id] = {
        'created_by': user_id,
        'created_by_username': username,
        'created_at': datetime.utcnow().isoformat(),
        'active': True
    }

    return jsonify({
        'success': True,
        'room_id': room_id,
        'join_url': f"http://localhost:5001/room/{room_id}"
    })

@app.route('/api/rooms/<room_id>')
def get_room(room_id):
    """Get room information"""
    if room_id not in video_rooms:
        return jsonify({'error': 'Room not found'}), 404

    room = video_rooms[room_id]
    return jsonify({
        'success': True,
        'room': {
            'room_id': room_id,
            'created_by': room['created_by_username'],
            'created_at': room['created_at'],
            'active': room.get('active', True),
            'participants': len(active_users.get(room_id, {}))
        }
    })

@app.route('/room/<room_id>')
def video_room(room_id):
    """Video chat room page"""
    if room_id not in video_rooms:
        return "Room not found", 404

    # Get user info from query params (passed from main server)
    username = request.args.get('username', 'Anonymous')
    user_id = request.args.get('user_id', '0')

    return render_template('video/room.html',
                         room_id=room_id,
                         username=username,
                         user_id=user_id,
                         server_port=5001)

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

    room_name = f"video_{room_id}"
    join_room(room_name)

    # Store user info
    if room_id not in active_users:
        active_users[room_id] = {}

    active_users[room_id][request.sid] = {
        'username': username,
        'user_id': user_id,
        'sid': request.sid,
        'audio_only': audio_only
    }

    # Notify others
    emit('user-joined', {
        'username': username,
        'sid': request.sid,
        'audio_only': audio_only
    }, room=room_name, include_self=False)

    # Send existing users list
    existing_users = [{
        'username': user['username'],
        'sid': sid,
        'audio_only': user.get('audio_only', False)
    } for sid, user in active_users[room_id].items() if sid != request.sid]

    emit('existing-users', {'users': existing_users}, room=request.sid)

@socketio.on('offer')
def handle_offer(data):
    """Handle WebRTC offer"""
    emit('offer', {
        'offer': data['offer'],
        'from': request.sid
    }, room=data['to'])

@socketio.on('answer')
def handle_answer(data):
    """Handle WebRTC answer"""
    emit('answer', {
        'answer': data['answer'],
        'from': request.sid
    }, room=data['to'])

@socketio.on('ice-candidate')
def handle_ice_candidate(data):
    """Handle ICE candidate"""
    emit('ice-candidate', {
        'candidate': data['candidate'],
        'from': request.sid
    }, room=data['to'])

@socketio.on('switch-camera')
def handle_switch_camera(data):
    """Handle camera switch"""
    room_id = data['room']
    emit('camera-switched', {
        'from': request.sid,
        'device_id': data.get('device_id')
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

@socketio.on('get-participants')
def handle_get_participants(data):
    """Get list of participants in a room"""
    room_id = data['room']

    if room_id in active_users:
        participants = [{
            'username': user['username'],
            'sid': sid,
            'audio_only': user.get('audio_only', False)
        } for sid, user in active_users[room_id].items()]

        emit('participants-list', {'participants': participants}, room=request.sid)

@socketio.on('leave')
def handle_leave(data):
    """Handle user leaving video room"""
    room_id = data['room']
    leave_room(f"video_{room_id}")

    if room_id in active_users and request.sid in active_users[room_id]:
        username = active_users[room_id][request.sid]['username']
        del active_users[room_id][request.sid]

        emit('user-left', {
            'username': username,
            'sid': request.sid
        }, room=f"video_{room_id}")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle socket disconnection"""
    for room_id in list(active_users.keys()):
        if request.sid in active_users[room_id]:
            username = active_users[room_id][request.sid]['username']
            del active_users[room_id][request.sid]

            emit('user-left', {
                'username': username,
                'sid': request.sid
            }, room=f"video_{room_id}")


def run():
    """Main function"""
    socketio.run(app, debug=True, port=app.config['PORT'])

if __name__ == '__main__':
    print(f"🚀 Video server starting on port {app.config['PORT']}")
    print(f"📡 WebSocket endpoint: http://localhost:{app.config['PORT']}")
    run()

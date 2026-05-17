import secrets
from datetime import datetime
from flask import Blueprint, request, jsonify

from app import db
from app.models import User, Call, VideoCall, VideoCallParticipant
from app.utils.helpers import get_current_user_id, get_current_user

spa_calls_bp = Blueprint('spa_calls', __name__, url_prefix='/api')

# ---- In-memory video room storage (temporary, without sockets) ----
video_rooms = {}

def generate_room_id():
    return secrets.token_urlsafe(12)[:16]

@spa_calls_bp.route('/calls/history', methods=['GET'])
def get_call_history():
    """Return the last 50 calls for the current user."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    calls = Call.query.filter(
        (Call.caller_id == user_id) | (Call.receiver_id == user_id)
    ).order_by(Call.created_at.desc()).limit(50).all()

    result = []
    for call in calls:
        contact_id = call.receiver_id if call.caller_id == user_id else call.caller_id
        contact = User.query.get(contact_id)
        result.append({
            'call_id': call.id,
            'contact_id': contact_id,
            'contact_name': contact.display_name if contact else None,
            'contact_username': contact.username if contact else None,
            'call_type': call.call_type,
            'status': call.status,
            'duration': call.duration,
            'is_outgoing': call.caller_id == user_id,
            'created_at': call.created_at.isoformat() if call.created_at else None
        })
    return jsonify({'success': True, 'calls': result})


@spa_calls_bp.route('/calls/make', methods=['POST'])
def make_call():
    """Initiate a call (audio/video) to another user. Stores a Call record, returns call_id."""
    caller_id = get_current_user_id()
    if not caller_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    data = request.get_json()
    receiver_id = data.get('receiver_id')
    call_type = data.get('call_type', 'audio')

    if not receiver_id:
        return jsonify({'success': False, 'error': 'receiver_id required'}), 400

    call = Call(caller_id=caller_id, receiver_id=receiver_id,
                call_type=call_type, status='ringing')
    db.session.add(call)
    db.session.commit()

    # In a real app, we would send a push notification or event via polling.
    # Since we removed socketio, the receiver can periodically check for new calls.
    return jsonify({'success': True, 'call_id': call.id})


@spa_calls_bp.route('/calls/answer', methods=['POST'])
def answer_call():
    """Mark a call as answered."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    data = request.get_json()
    call_id = data.get('call_id')
    call = Call.query.get(call_id)
    if not call:
        return jsonify({'success': False, 'error': 'Call not found'}), 404

    call.status = 'answered'
    db.session.commit()
    return jsonify({'success': True})


@spa_calls_bp.route('/calls/end', methods=['POST'])
def end_call():
    """End a call with optional duration."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    data = request.get_json()
    call_id = data.get('call_id')
    duration = data.get('duration', 0)
    call = Call.query.get(call_id)
    if call:
        call.status = 'ended'
        call.duration = duration
        db.session.commit()
    return jsonify({'success': True})


# ---- Video room endpoints (no socketio, just HTTP) ----
@spa_calls_bp.route('/video/create_room', methods=['POST'])
def create_room():
    """Create a new WebRTC video room (returns room_id)."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    room_id = generate_room_id()
    call_type = request.json.get('call_type', 'video') if request.is_json else 'video'

    video_rooms[room_id] = {
        'creator_id': user_id,
        'creator_name': get_current_user().display_name or get_current_user().username,
        'participants': {},
        'created_at': datetime.utcnow().isoformat(),
        'call_type': call_type
    }

    # Persist in database
    vc = VideoCall(room_id=room_id, creator_id=user_id, call_type=call_type, status='active')
    db.session.add(vc)
    db.session.commit()

    # Join creator as participant
    join_call_record(room_id, user_id)

    return jsonify({'success': True, 'room_id': room_id})


@spa_calls_bp.route('/video/join/<room_id>', methods=['POST'])
def join_room(room_id):
    """Join an existing video room."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    if room_id not in video_rooms:
        return jsonify({'success': False, 'error': 'Room not found'}), 404

    audio_only = request.json.get('audio_only', False) if request.is_json else False
    join_call_record(room_id, user_id, audio_only)

    return jsonify({'success': True, 'room': video_rooms[room_id]})


@spa_calls_bp.route('/video/end/<room_id>', methods=['POST'])
def end_room(room_id):
    """End a video room (only the creator can end it)."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    if room_id not in video_rooms:
        return jsonify({'success': False, 'error': 'Room not found'}), 404

    if video_rooms[room_id]['creator_id'] != user_id:
        return jsonify({'success': False, 'error': 'Only the creator can end the room'}), 403

    # Update DB
    vc = VideoCall.query.filter_by(room_id=room_id, status='active').first()
    if vc:
        vc.status = 'ended'
        vc.ended_at = datetime.utcnow()
        vc.duration = (datetime.utcnow() - vc.started_at).seconds if vc.started_at else 0
        db.session.commit()

    # No socketio emit; clients poll or use video server events
    del video_rooms[room_id]
    return jsonify({'success': True})


# Helper
def join_call_record(room_id, user_id, audio_only=False):
    """Add a participant to the in-memory room and database."""
    if 'participants' not in video_rooms[room_id]:
        video_rooms[room_id]['participants'] = {}
    video_rooms[room_id]['participants'][str(user_id)] = {
        'user_id': user_id,
        'username': get_current_user().username if get_current_user() else 'Unknown',
        'audio_only': audio_only
    }
    vc = VideoCall.query.filter_by(room_id=room_id, status='active').first()
    if vc:
        vcp = VideoCallParticipant(call_id=vc.id, user_id=user_id, audio_only=audio_only)
        db.session.add(vcp)
        db.session.commit()
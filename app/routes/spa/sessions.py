from flask import Blueprint, request, jsonify, session
from app import db
from app.models import UserSession
from app.utils.helpers import get_current_user_id

spa_sessions_bp = Blueprint('spa_sessions', __name__, url_prefix='/api')

@spa_sessions_bp.route('/sessions', methods=['GET'])
def get_sessions():
    """List all active sessions for the current user."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    sessions = UserSession.query.filter_by(user_id=user_id, is_active=True).order_by(UserSession.last_activity.desc()).all()
    result = []
    for s in sessions:
        result.append({
            'id': s.id,
            'session_token': s.session_token,
            'device': getattr(s, 'device', 'Unknown'),
            'ip': s.ip_address,
            'location': getattr(s, 'location', ''),
            'created_at': s.created_at.isoformat() if s.created_at else None,
            'last_activity': s.last_activity.isoformat() if s.last_activity else None
        })
    return jsonify({'success': True, 'sessions': result})

@spa_sessions_bp.route('/sessions/terminate', methods=['POST'])
def terminate_session():
    """Terminate a specific session (except the current one)."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    data = request.get_json()
    session_token = data.get('session_token')
    current_token = session.get('session_token')

    if session_token == current_token:
        return jsonify({'success': False, 'error': 'Cannot terminate current session'}), 400

    s = UserSession.query.filter_by(session_token=session_token, user_id=user_id).first()
    if s:
        db.session.delete(s)
        db.session.commit()
    return jsonify({'success': True})

@spa_sessions_bp.route('/sessions/terminate_all', methods=['POST'])
def terminate_all_sessions():
    """Terminate all other sessions, keep the current one."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    current_token = session.get('session_token')
    UserSession.query.filter(UserSession.user_id == user_id,
                             UserSession.session_token != current_token).delete()
    db.session.commit()
    return jsonify({'success': True})
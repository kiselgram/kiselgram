import re
from datetime import datetime
from flask import Blueprint, request, jsonify, session
from app import db
from app.models import User
from app.utils.helpers import get_current_user_id, get_current_user

spa_auth_bp = Blueprint('spa_auth', __name__, url_prefix='/api')

@spa_auth_bp.route('/auth/logout', methods=['POST'])
def spa_logout():
    user_id = session.get('user_id')
    if user_id:
        user = User.query.get(user_id)
        if user:
            user.is_online = False
            user.last_seen = datetime.utcnow()
            db.session.commit()
    session.clear()
    return jsonify({'success': True})

@spa_auth_bp.route('/check_username', methods=['POST'])
def check_username():
    if not get_current_user():
        return jsonify({'error': 'Not authenticated'}), 401
    data = request.get_json()
    username = data.get('username', '').strip()
    if len(username) < 3:
        return jsonify({'available': False, 'message': 'Min 3 characters'})
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return jsonify({'available': False, 'message': 'Only letters, numbers, underscores'})
    current_user_id = get_current_user_id()
    existing = User.query.filter_by(username=username).first()
    if existing and existing.id != current_user_id:
        return jsonify({'available': False, 'message': 'Username taken'})
    return jsonify({'available': True, 'message': 'Available'})

@spa_auth_bp.route('/update_last_seen', methods=['POST'])
def update_last_seen():
    """Periodically updated by frontend to refresh last seen timestamp."""
    user_id = session.get('user_id')
    if user_id:
        user = User.query.get(user_id)
        if user:
            user.last_seen = datetime.utcnow()
            db.session.commit()
    return jsonify({'success': True})
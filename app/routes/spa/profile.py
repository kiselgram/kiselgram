import os
import re
import secrets
from flask import Blueprint, request, jsonify, session
from werkzeug.utils import secure_filename

from app import db
from app.models import User
from app.utils.helpers import get_current_user_id, get_current_user

spa_profile_bp = Blueprint('spa_profile', __name__, url_prefix='/api')

@spa_profile_bp.route('/profile', methods=['GET'])
def get_my_profile():
    """
    Return the current user's profile information.
    """
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    return jsonify({
        'success': True,
        'user': {
            'id': user.id,
            'username': user.username,
            'display_name': user.display_name or user.username,
            'bio': user.bio or '',
            'avatar_url': user.avatar_url,
            'email': getattr(user, 'email', ''),
            'is_premium': getattr(user, 'is_premium', False),
            'is_admin': getattr(user, 'is_admin', False),
            'created_at': user.created_at.isoformat() if user.created_at else None,
            'last_seen': user.last_seen.isoformat() if user.last_seen else None,
            'is_online': getattr(user, 'is_online', False),
            'status_emoji': getattr(user, 'status_emoji', ''),
            'followers_count': 0,   # implement later
            'following_count': 0,
            'groups_count': 0
        }
    })

@spa_profile_bp.route('/profile/update', methods=['PUT'])
def update_profile():
    """
    Update the current user's profile fields: display_name, username, bio.
    """
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    data = request.get_json()
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    if 'display_name' in data:
        display_name = data['display_name'].strip()
        if display_name:
            user.display_name = display_name[:80]
    if 'bio' in data:
        bio = data['bio'].strip()
        user.bio = bio[:500] if bio else None
    if 'username' in data:
        new_username = data['username'].strip().lower()
        if len(new_username) >= 3 and re.match(r'^[a-zA-Z0-9_]+$', new_username):
            existing = User.query.filter_by(username=new_username).first()
            if not existing or existing.id == user_id:
                user.username = new_username
                session['username'] = new_username
            else:
                return jsonify({'success': False, 'error': 'Username taken'}), 400
        else:
            return jsonify({'success': False, 'error': 'Invalid username'}), 400

    db.session.commit()
    return jsonify({'success': True, 'message': 'Profile updated'})

@spa_profile_bp.route('/profile/avatar', methods=['POST'])
def upload_avatar():
    """
    Upload a new avatar image.
    """
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    if 'avatar' not in request.files:
        return jsonify({'success': False, 'error': 'No file'}), 400

    file = request.files['avatar']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400

    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
    if ext not in ('jpg', 'jpeg', 'png', 'gif', 'webp'):
        return jsonify({'success': False, 'error': 'Invalid format'}), 400

    filename = f"avatar_{user_id}_{secrets.token_urlsafe(4)}.{ext}"
    upload_dir = os.path.join('uploads', 'avatars')
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, filename)
    file.save(file_path)

    user = User.query.get(user_id)
    # Delete old avatar if it exists
    if user.avatar_url and 'uploads/' in user.avatar_url:
        old_path = os.path.join(user.avatar_url.replace('/uploads/', 'uploads/'))
        if os.path.exists(old_path):
            os.remove(old_path)

    user.avatar_url = f"/uploads/avatars/{filename}"
    db.session.commit()

    return jsonify({'success': True, 'avatar_url': user.avatar_url})

@spa_profile_bp.route('/profile/settings', methods=['GET', 'PUT'])
def user_settings():
    """
    GET: return current settings (theme, font_size, bubble_radius, font_family, colors, wallpaper).
    PUT: update one or more settings.
    """
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    if request.method == 'GET':
        return jsonify({
            'success': True,
            'settings': {
                'theme': getattr(user, 'theme', 'light'),
                'font_size': getattr(user, 'font_size', 14),
                'bubble_radius': getattr(user, 'bubble_radius', 18),
                'font_family': getattr(user, 'font_family', "'Inter', sans-serif"),
                'my_message_color': getattr(user, 'my_message_color', '#667eea'),
                'their_message_color': getattr(user, 'their_message_color', '#f3f4f6'),
                'wallpaper': getattr(user, 'wallpaper', ''),
                'wallpaper_image': getattr(user, 'wallpaper_image', '')
            }
        })

    data = request.get_json()
    if 'theme' in data: user.theme = data['theme']
    if 'font_size' in data: user.font_size = data['font_size']
    if 'bubble_radius' in data: user.bubble_radius = data['bubble_radius']
    if 'font_family' in data: user.font_family = data['font_family']
    if 'my_message_color' in data: user.my_message_color = data['my_message_color']
    if 'their_message_color' in data: user.their_message_color = data['their_message_color']
    if 'wallpaper' in data: user.wallpaper = data['wallpaper']

    db.session.commit()
    return jsonify({'success': True, 'message': 'Settings updated'})

@spa_profile_bp.route('/profile/privacy', methods=['GET', 'PUT'])
def privacy_settings():
    """
    Get/update privacy settings (last_seen, profile_photo, calls, messages, forward).
    """
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    if request.method == 'GET':
        return jsonify({
            'success': True,
            'privacy': {
                'last_seen': getattr(user, 'privacy_last_seen', 'everyone'),
                'profile_photo': getattr(user, 'privacy_photo', 'everyone'),
                'calls': getattr(user, 'privacy_calls', 'everyone'),
                'messages': getattr(user, 'privacy_messages', 'everyone'),
                'forward': getattr(user, 'privacy_forward', 'everyone')
            }
        })

    data = request.get_json()
    if 'last_seen' in data: user.privacy_last_seen = data['last_seen']
    if 'profile_photo' in data: user.privacy_photo = data['profile_photo']
    if 'calls' in data: user.privacy_calls = data['calls']  # was data['privacy_calls']
    if 'messages' in data: user.privacy_messages = data['messages']  # was data['privacy_messages']
    if 'forward' in data: user.privacy_forward = data['forward']
    db.session.commit()
    return jsonify({'success': True, 'message': 'Privacy updated'})
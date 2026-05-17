# Update utils/helpers.py

import hashlib
import secrets
import os
import re
from datetime import datetime, timedelta
from PIL import Image
from app.models import Story, BlockedUser, GroupMember, Message, Forward, Reply, Reaction


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def get_current_user():
    from flask import session
    from app.models import User
    user_id = session.get('user_id')
    if user_id:
        return User.query.get(user_id)
    return None


def get_current_user_id():
    from flask import session
    return session.get('user_id')


def generate_invite_link():
    return secrets.token_urlsafe(16)


def format_file_size(size_bytes):
    """Convert bytes to human readable format"""
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1

    return f"{size_bytes:.1f} {size_names[i]}"


def format_timestamp(dt):
    """Format datetime for display"""
    if not dt:
        return ''

    now = datetime.utcnow()
    diff = now - dt

    if diff.days == 0:
        return dt.strftime('%H:%M')
    elif diff.days == 1:
        return 'Yesterday'
    elif diff.days < 7:
        return dt.strftime('%A')
    else:
        return dt.strftime('%d.%m.%Y')


def highlight_text(text, query):
    if not text or not query:
        return text
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    return pattern.sub(lambda m: f'<span class="highlight">{m.group()}</span>', str(text))


def allowed_file(filename, allowed_extensions=None):
    """Check if file extension is allowed"""
    if '.' not in filename:
        return False

    ext = filename.rsplit('.', 1)[1].lower()

    if allowed_extensions is None:
        allowed_extensions = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'pdf', 'doc', 'docx', 'txt', 'mp3', 'mp4', 'zip'}

    return ext in allowed_extensions


def get_file_type(filename):
    """Determine file type from extension"""
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

    image_extensions = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'}
    audio_extensions = {'mp3', 'wav', 'ogg', 'm4a'}
    video_extensions = {'mp4', 'avi', 'mov', 'mkv', 'webm'}
    document_extensions = {'pdf', 'doc', 'docx', 'txt', 'rtf'}
    archive_extensions = {'zip', 'rar', '7z'}

    if ext in image_extensions:
        return 'image'
    elif ext in audio_extensions:
        return 'audio'
    elif ext in video_extensions:
        return 'video'
    elif ext in document_extensions:
        return 'document'
    elif ext in archive_extensions:
        return 'archive'
    else:
        return 'other'


def create_thumbnail(image_path, thumbnail_path, size=(200, 200)):
    """Create thumbnail for images"""
    try:
        with Image.open(image_path) as img:
            img.thumbnail(size)
            img.save(thumbnail_path, 'JPEG' if thumbnail_path.lower().endswith('.jpg') else 'PNG')
        return True
    except Exception as e:
        print(f"Thumbnail creation failed: {e}")
        return False




def get_blocked_user_ids(user_id):
    try:
        blocks = BlockedUser.query.filter_by(user_id=user_id).all()
        return [b.blocked_user_id for b in blocks]
    except:
        return []

def has_active_story(user_id):
    try:
        cutoff = datetime.utcnow() - timedelta(hours=24)
        return Story.query.filter(
            Story.user_id == user_id,
            Story.created_at >= cutoff
        ).count() > 0
    except:
        return False

def user_to_dict(user):
    return {
        'id': user.id,
        'username': user.username,
        'display_name': user.display_name or user.username,
        'bio': user.bio,
        'avatar_url': user.avatar_url,
        'is_online': getattr(user, 'is_online', False),
        'last_seen': user.last_seen.isoformat() if user.last_seen else None,
        'created_at': user.created_at.isoformat() if user.created_at else None,
        'has_story': has_active_story(user.id),
        'is_premium': getattr(user, 'is_premium', False),
        'status_emoji': getattr(user, 'status_emoji', ''),
        'followers_count': 0,
        'following_count': 0,
        'groups_count': GroupMember.query.filter_by(user_id=user.id).count()
    }

def message_to_dict(message, current_user_id):
    msg_data = {
        'id': message.id,
        'content': message.content,
        'sender_id': message.sender_id,
        'sender_name': message.sender.username if message.sender else 'Unknown',
        'timestamp': message.timestamp.isoformat() if message.timestamp else None,
        'timestamp_formatted': message.timestamp.strftime('%H:%M') if message.timestamp else '',
        'is_own': message.sender_id == current_user_id,
        'is_read': message.is_read,
        'has_attachment': message.has_attachment,
        'reply_to_id': None,
        'reply_to_content': None,
        'reply_to_sender': None,
        'forwarded_from': None,
        'reactions': {}
    }

    if message.has_attachment:
        msg_data['file_type'] = message.file_type
        msg_data['file_name'] = message.file_name
        msg_data['file_size'] = message.file_size
        msg_data['formatted_size'] = format_file_size(message.file_size) if message.file_size else '0 B'
        msg_data['file_url'] = f"/uploads/{message.file_path}" if message.file_path else None

    reply = Reply.query.filter_by(reply_message_id=message.id).first()
    if reply:
        original = Message.query.get(reply.original_message_id)
        if original:
            msg_data['reply_to_id'] = original.id
            msg_data['reply_to_content'] = original.content[:50] if original.content else ''
            msg_data['reply_to_sender'] = original.sender.username if original.sender else ''

    forward = Forward.query.filter_by(forwarded_message_id=message.id).first()
    if forward:
        msg_data['forwarded_from'] = forward.original_sender_name

    reactions = Reaction.query.filter_by(message_id=message.id).all()
    for r in reactions:
        if r.reaction_type not in msg_data['reactions']:
            msg_data['reactions'][r.reaction_type] = 0
        msg_data['reactions'][r.reaction_type] += 1

    return msg_data
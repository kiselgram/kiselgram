# Update utils/helpers.py

import hashlib
import secrets
import os
import re
from datetime import datetime
from PIL import Image


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
import hashlib
import secrets
import os
import re
from PIL import Image


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def get_current_user():
    from flask import session
    return session.get('username')


def get_current_user_id():
    from flask import session
    return session.get('user_id')


def generate_invite_link():
    return secrets.token_urlsafe(16)


def allowed_file(filename, file_type='all'):
    """Check if file extension is allowed"""
    from flask import current_app  # Use current_app instead of importing app

    if '.' not in filename:
        return False

    ext = filename.rsplit('.', 1)[1].lower()

    if file_type == 'all':
        for category in current_app.config['ALLOWED_EXTENSIONS'].values():
            if ext in category:
                return True
        return False
    elif file_type in current_app.config['ALLOWED_EXTENSIONS']:
        return ext in current_app.config['ALLOWED_EXTENSIONS'][file_type]

    return False


def get_file_type(filename):
    """Determine file type from extension"""
    from app import create_app

    app = create_app()

    ext = filename.rsplit('.', 1)[1].lower()

    if ext in app.config['ALLOWED_EXTENSIONS']['images']:
        return 'image'
    elif ext in app.config['ALLOWED_EXTENSIONS']['media']:
        if ext in {'mp4', 'avi', 'mov', 'mkv'}:
            return 'video'
        return 'audio'
    elif ext in app.config['ALLOWED_EXTENSIONS']['documents']:
        return 'document'
    elif ext in app.config['ALLOWED_EXTENSIONS']['archives']:
        return 'archive'
    else:
        return 'unknown'

    app = None


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


def highlight_text(text, query):
    if not text or not query:
        return text
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    return pattern.sub(lambda m: f'<span class="highlight">{m.group()}</span>', str(text))
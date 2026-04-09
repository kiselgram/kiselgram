from flask import Blueprint, request, jsonify, send_file, current_app, url_for, session
import os
import uuid
import mimetypes
from app import db
from app.models import User, Message, Group, Channel, GroupMember, ChannelSubscriber
from datetime import datetime

files_bp = Blueprint('files', __name__)



def allowed_file(filename):
    """Check if file extension is allowed"""
    if '.' not in filename:
        return False

    ext = filename.rsplit('.', 1)[1].lower()

    allowed_extensions = {
        'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp',  # images
        'pdf', 'doc', 'docx', 'txt', 'rtf',  # documents
        'zip', 'rar', '7z',  # archives
        'mp3', 'mp4', 'm4a', 'wav', 'ogg', 'avi', 'mov', 'mkv'  # media
    }

    return ext in allowed_extensions


def get_file_type(filename):
    """Determine file type based on extension"""
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


def format_file_size(bytes):
    """Format file size in human readable format"""
    if bytes == 0:
        return '0 B'

    size_names = ['B', 'KB', 'MB', 'GB']
    i = 0
    while bytes >= 1024 and i < len(size_names) - 1:
        bytes /= 1024
        i += 1

    return f"{bytes:.1f} {size_names[i]}"


@files_bp.route('/uploads/<path:filename>')
def serve_file(filename):
    """Serve uploaded files"""
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        base_upload_dir = os.path.join(os.path.dirname(current_dir), 'uploads')
        file_path = os.path.join(base_upload_dir, filename)
        file_path = os.path.normpath(file_path)

        if not file_path.startswith(base_upload_dir):
            return "Invalid file path", 403

        if os.path.exists(file_path) and os.path.isfile(file_path):
            mimetype, _ = mimetypes.guess_type(filename)
            return send_file(file_path, mimetype=mimetype)

        # Try alternative paths
        base_filename = os.path.basename(filename)
        alternative_paths = [
            os.path.join(base_upload_dir, 'images', base_filename),
            os.path.join(base_upload_dir, 'documents', base_filename),
            os.path.join(base_upload_dir, 'media', base_filename),
            os.path.join(base_upload_dir, 'stories', base_filename),
            os.path.join(base_upload_dir, base_filename)
        ]

        for alt_path in alternative_paths:
            alt_path = os.path.normpath(alt_path)
            if os.path.exists(alt_path) and os.path.isfile(alt_path):
                mimetype, _ = mimetypes.guess_type(base_filename)
                return send_file(alt_path, mimetype=mimetype)

        return "File not found", 404
    except Exception as e:
        print(f"Error serving file: {str(e)}")
        return str(e), 500


@files_bp.route('/files/upload_file', methods=['POST'])
def upload_file():
    """Handle file uploads for personal chats, groups, and channels"""
    # Get current user from session
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    current_user = User.query.get(user_id)
    if not current_user:
        return jsonify({'success': False, 'error': 'User not found'}), 401

    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'success': False, 'error': 'File type not allowed'}), 400

    # Get target IDs from form data
    receiver_id = request.form.get('receiver_id')
    group_id = request.form.get('group_id')
    channel_id = request.form.get('channel_id')
    message_text = request.form.get('message', '')

    # Validate that at least one target is specified
    if not receiver_id and not group_id and not channel_id:
        return jsonify({'success': False, 'error': 'No receiver, group, or channel specified'}), 400

    try:
        # Verify permissions
        if receiver_id:
            receiver = User.query.get(receiver_id)
            if not receiver:
                return jsonify({'success': False, 'error': 'Receiver not found'}), 404
            # Check if blocked
            from app.models import BlockedUser
            if BlockedUser.query.filter_by(user_id=receiver_id, blocked_user_id=user_id).first():
                return jsonify({'success': False, 'error': 'You are blocked by this user'}), 403

        elif group_id:
            group = Group.query.get(group_id)
            if not group:
                return jsonify({'success': False, 'error': 'Group not found'}), 404
            # Check if member
            membership = GroupMember.query.filter_by(user_id=user_id, group_id=group_id).first()
            if not membership:
                return jsonify({'success': False, 'error': 'You are not a member of this group'}), 403

        elif channel_id:
            channel = Channel.query.get(channel_id)
            if not channel:
                return jsonify({'success': False, 'error': 'Channel not found'}), 404
            # Check if owner (only owner can post to channel)
            if channel.owner_id != user_id:
                return jsonify({'success': False, 'error': 'Only channel owner can post'}), 403

        # Generate unique filename
        file_ext = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{file_ext}"
        file_type = get_file_type(file.filename)

        # Determine upload directory
        if file_type == 'image':
            upload_dir = 'images'
        elif file_type in ['audio', 'video']:
            upload_dir = 'media'
        else:
            upload_dir = 'documents'

        # Save file
        file_path_with_dir = os.path.join(upload_dir, unique_filename)

        current_dir = os.path.dirname(os.path.abspath(__file__))
        base_upload_dir = os.path.join(os.path.dirname(current_dir), 'uploads')
        full_save_path = os.path.join(base_upload_dir, file_path_with_dir)

        os.makedirs(os.path.dirname(full_save_path), exist_ok=True)
        file.save(full_save_path)

        file_size = os.path.getsize(full_save_path)
        file_url = url_for('files.serve_file', filename=file_path_with_dir, _external=False)

        # Create message in database
        new_message = Message(
            sender_id=current_user.id,
            content=message_text,
            has_attachment=True,
            file_name=file.filename,
            file_path=file_path_with_dir,
            file_type=file_type,
            file_size=file_size,
            timestamp=datetime.utcnow(),
            is_read=False
        )

        # Set the appropriate target
        if receiver_id:
            new_message.receiver_id = int(receiver_id)
        elif group_id:
            new_message.group_id = int(group_id)
            new_message.receiver_id = current_user.id  # Placeholder
        elif channel_id:
            new_message.channel_id = int(channel_id)
            new_message.receiver_id = current_user.id  # Placeholder

        db.session.add(new_message)
        db.session.commit()

        # Prepare response
        message_data = {
            'id': new_message.id,
            'content': message_text,
            'sender_id': current_user.id,
            'sender_name': current_user.username,
            'timestamp': new_message.timestamp.isoformat(),
            'timestamp_formatted': new_message.timestamp.strftime('%H:%M'),
            'is_own': True,
            'is_read': False,
            'has_attachment': True,
            'file_name': file.filename,
            'file_url': file_url,
            'file_type': file_type,
            'file_size': file_size,
            'formatted_size': format_file_size(file_size)
        }

        return jsonify({
            'success': True,
            'filename': unique_filename,
            'url': file_url,
            'message': message_data
        })

    except Exception as e:
        print(f"Upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@files_bp.route('/files/upload_avatar', methods=['POST'])
def upload_avatar():
    """Handle avatar upload for user profile"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    current_user = User.query.get(user_id)
    if not current_user:
        return jsonify({'success': False, 'error': 'User not found'}), 401

    if 'avatar' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400

    file = request.files['avatar']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400

    allowed_image_types = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
    file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''

    if file_ext not in allowed_image_types:
        return jsonify({'success': False, 'error': 'Invalid image format'}), 400

    try:
        from PIL import Image

        image = Image.open(file)

        # Convert RGBA to RGB
        if image.mode in ('RGBA', 'P'):
            rgb_image = Image.new('RGB', image.size, (255, 255, 255))
            rgb_image.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
            image = rgb_image

        # Resize
        max_size = (400, 400)
        image.thumbnail(max_size, Image.Resampling.LANCZOS)

        unique_filename = f"avatar_{uuid.uuid4().hex}.jpg"

        current_dir = os.path.dirname(os.path.abspath(__file__))
        base_upload_dir = os.path.join(os.path.dirname(current_dir), 'uploads')
        avatars_dir = os.path.join(base_upload_dir, 'avatars')
        os.makedirs(avatars_dir, exist_ok=True)

        file_path = os.path.join(avatars_dir, unique_filename)
        relative_path = os.path.join('avatars', unique_filename)

        image.save(file_path, 'JPEG', quality=85)

        # Delete old avatar
        if current_user.avatar_url:
            old_avatar_path = os.path.join(base_upload_dir, current_user.avatar_url.replace('/uploads/', ''))
            if os.path.exists(old_avatar_path):
                os.remove(old_avatar_path)

        current_user.avatar_url = f"/uploads/{relative_path}"
        db.session.commit()

        return jsonify({
            'success': True,
            'avatar_url': current_user.avatar_url,
            'message': 'Avatar updated successfully'
        })

    except Exception as e:
        print(f"Avatar upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@files_bp.route('/files/upload_story', methods=['POST'])
def upload_story():
    """Upload a story media file"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    if 'media' not in request.files:
        return jsonify({'success': False, 'error': 'No media provided'}), 400

    file = request.files['media']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400

    file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''

    if file_ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
        media_type = 'image'
    elif file_ext in ['mp4', 'mov', 'avi', 'webm']:
        media_type = 'video'
    else:
        return jsonify({'success': False, 'error': 'Unsupported media type'}), 400

    try:
        unique_filename = f"story_{uuid.uuid4().hex}.{file_ext}"

        current_dir = os.path.dirname(os.path.abspath(__file__))
        base_upload_dir = os.path.join(os.path.dirname(current_dir), 'uploads')
        stories_dir = os.path.join(base_upload_dir, 'stories')
        os.makedirs(stories_dir, exist_ok=True)

        file_path = os.path.join(stories_dir, unique_filename)
        relative_path = os.path.join('stories', unique_filename)

        file.save(file_path)

        from app.models import Story

        new_story = Story(
            user_id=user_id,
            media_path=relative_path,
            media_type=media_type,
            caption=request.form.get('caption', '')
        )
        db.session.add(new_story)
        db.session.commit()

        return jsonify({
            'success': True,
            'story': {
                'id': new_story.id,
                'media_url': f"/uploads/{relative_path}",
                'media_type': media_type
            }
        })

    except Exception as e:
        print(f"Story upload error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@files_bp.route('/files/delete_file/<int:message_id>', methods=['DELETE'])
def delete_file(message_id):
    """Delete a file message"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    message = Message.query.get_or_404(message_id)

    if message.sender_id != user_id:
        return jsonify({'success': False, 'error': 'Not authorized'}), 403

    try:
        if message.file_path:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            base_upload_dir = os.path.join(os.path.dirname(current_dir), 'uploads')
            file_path = os.path.join(base_upload_dir, message.file_path)
            if os.path.exists(file_path):
                os.remove(file_path)

        db.session.delete(message)
        db.session.commit()

        return jsonify({'success': True, 'message': 'File deleted'})

    except Exception as e:
        print(f"Delete error: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
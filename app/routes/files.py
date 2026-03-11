from flask import Blueprint, request, jsonify, send_file, current_app, url_for
import os
import uuid
import mimetypes
from app import db
from app.models import User, Message
from datetime import datetime

files_bp = Blueprint('files', __name__)


def allowed_file(filename):
    """Check if file extension is allowed"""
    if '.' not in filename:
        return False

    ext = filename.rsplit('.', 1)[1].lower()

    # Define allowed extensions locally
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
        print(f"🔍 DEBUG - Serving file: {filename}")
        print(f"🔍 DEBUG - Request URL: {request.url}")
        print(f"🔍 DEBUG - Request headers: {dict(request.headers)}")

        # Get the absolute path to the uploads directory
        # This assumes your files.py is in a subdirectory like 'routes' or 'blueprints'
        current_dir = os.path.dirname(os.path.abspath(__file__))
        base_upload_dir = os.path.join(os.path.dirname(current_dir), 'uploads')

        print(f"🔍 DEBUG - Current dir: {current_dir}")
        print(f"🔍 DEBUG - Base upload dir: {base_upload_dir}")

        # Construct the full path
        file_path = os.path.join(base_upload_dir, filename)
        file_path = os.path.normpath(file_path)

        print(f"🔍 DEBUG - Full path: {file_path}")
        print(f"🔍 DEBUG - File exists: {os.path.exists(file_path)}")

        # Security check: make sure the path is within uploads directory
        if not file_path.startswith(base_upload_dir):
            print(f"🔍 DEBUG - Security violation: {file_path} not in {base_upload_dir}")
            return "Invalid file path", 403

        if os.path.exists(file_path) and os.path.isfile(file_path):
            # Try to determine the correct mimetype
            mimetype, _ = mimetypes.guess_type(filename)
            print(f"🔍 DEBUG - Sending file with mimetype: {mimetype}")
            return send_file(file_path, mimetype=mimetype)

        # If not found, try without the subdirectory (for backward compatibility)
        base_filename = os.path.basename(filename)
        alternative_paths = [
            os.path.join(base_upload_dir, 'images', base_filename),
            os.path.join(base_upload_dir, 'documents', base_filename),
            os.path.join(base_upload_dir, 'media', base_filename),
            os.path.join(base_upload_dir, base_filename)
        ]

        for alt_path in alternative_paths:
            alt_path = os.path.normpath(alt_path)
            print(f"🔍 DEBUG - Trying alternative: {alt_path}")
            if os.path.exists(alt_path) and os.path.isfile(alt_path):
                print(f"🔍 DEBUG - Found at alternative path")
                mimetype, _ = mimetypes.guess_type(base_filename)
                return send_file(alt_path, mimetype=mimetype)

        print(f"🔍 DEBUG - File not found: {filename}")
        return "File not found", 404
    except Exception as e:
        print(f"🔍 DEBUG - Error serving file: {str(e)}")
        return str(e), 500


@files_bp.route('/upload_file', methods=['POST'])
def upload_file():
    """Handle file uploads"""
    from flask import session

    print("🔍 DEBUG - Upload file endpoint called")
    print(f"🔍 DEBUG - Request files: {request.files}")
    print(f"🔍 DEBUG - Request form: {request.form}")

    # Get current user from session
    user_id = session.get('user_id')
    if not user_id:
        print("🔍 DEBUG - Not authenticated")
        return jsonify({'error': 'Not authenticated'}), 401

    current_user = User.query.get(user_id)
    if not current_user:
        print(f"🔍 DEBUG - User not found: {user_id}")
        return jsonify({'error': 'User not found'}), 401

    print(f"🔍 DEBUG - Current user: {current_user.username} (ID: {current_user.id})")

    if 'file' not in request.files:
        print("🔍 DEBUG - No file provided")
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        print("🔍 DEBUG - No file selected")
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        print(f"🔍 DEBUG - File type not allowed: {file.filename}")
        return jsonify({'error': 'File type not allowed'}), 400

    # Get receiver_id from form data
    receiver_id = request.form.get('receiver_id')
    if not receiver_id:
        print("🔍 DEBUG - No receiver specified")
        return jsonify({'error': 'No receiver specified'}), 400

    # Verify receiver exists
    receiver = User.query.get(receiver_id)
    if not receiver:
        print(f"🔍 DEBUG - Receiver not found: {receiver_id}")
        return jsonify({'error': 'Receiver not found'}), 404

    print(f"🔍 DEBUG - Receiver: {receiver.username} (ID: {receiver.id})")

    message_text = request.form.get('message', '')
    print(f"🔍 DEBUG - Message text: {message_text}")

    try:
        # Generate unique filename
        file_ext = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{file_ext}"
        file_type = get_file_type(file.filename)

        print(f"🔍 DEBUG - Unique filename: {unique_filename}")
        print(f"🔍 DEBUG - File type: {file_type}")

        # Determine upload directory
        if file_type == 'image':
            upload_dir = 'images'
        elif file_type in ['audio', 'video']:
            upload_dir = 'media'
        else:
            upload_dir = 'documents'

        print(f"🔍 DEBUG - Upload directory: {upload_dir}")

        # Save file with full path including subdirectory in filename
        file_path_with_dir = os.path.join(upload_dir, unique_filename)

        # Get the absolute path for saving
        current_dir = os.path.dirname(os.path.abspath(__file__))
        base_upload_dir = os.path.join(os.path.dirname(current_dir), 'uploads')
        full_save_path = os.path.join(base_upload_dir, file_path_with_dir)

        print(f"🔍 DEBUG - Current dir: {current_dir}")
        print(f"🔍 DEBUG - Base upload dir: {base_upload_dir}")
        print(f"🔍 DEBUG - Full save path: {full_save_path}")

        # Create the URL - using relative URL to avoid domain issues
        file_url = url_for('files.serve_file', filename=file_path_with_dir, _external=False)

        # Also create an absolute URL for debugging
        absolute_url = url_for('files.serve_file', filename=file_path_with_dir, _external=True)

        print(f"🔍 DEBUG - File URL (relative): {file_url}")
        print(f"🔍 DEBUG - File URL (absolute): {absolute_url}")
        print(f"🔍 DEBUG - Blueprint endpoint: files.serve_file")

        # Create directories if they don't exist
        os.makedirs(os.path.dirname(full_save_path), exist_ok=True)
        print(f"🔍 DEBUG - Created directory: {os.path.dirname(full_save_path)}")

        # Save the file
        file.save(full_save_path)
        print(f"🔍 DEBUG - File saved successfully")

        # Get file size
        file_size = os.path.getsize(full_save_path)
        print(f"🔍 DEBUG - File size: {file_size} bytes")

        # Generate thumbnail path for images (optional)
        thumbnail_path = None
        if file_type == 'image':
            thumbnail_path = file_url

        # Create a message in the database for this file
        new_message = Message(
            sender_id=current_user.id,
            receiver_id=receiver_id,
            content=message_text,
            has_attachment=True,
            file_name=file.filename,
            file_path=file_path_with_dir,  # Store the relative path with subdirectory
            file_type=file_type,
            file_size=file_size,
            thumbnail_path=thumbnail_path,
            timestamp=datetime.utcnow(),
            is_read=False
        )

        db.session.add(new_message)
        db.session.commit()

        print(f"🔍 DEBUG - Message created with ID: {new_message.id}")

        # Prepare message data for frontend
        message_data = {
            'id': new_message.id,
            'content': message_text,
            'sender_name': current_user.username,
            'timestamp': new_message.timestamp.strftime('%H:%M'),
            'is_own': True,
            'is_read': False,
            'has_attachment': True,
            'file_name': file.filename,
            'file_url': file_url,  # Use the relative URL
            'file_type': file_type,
            'file_size': file_size,
            'formatted_size': format_file_size(file_size)
        }

        # Add thumbnail URL for images
        if file_type == 'image' and thumbnail_path:
            message_data['thumbnail_url'] = thumbnail_path

        print(f"🔍 DEBUG - Response data: {message_data}")

        return jsonify({
            'success': True,
            'filename': unique_filename,
            'url': file_url,
            'message': message_data
        })

    except Exception as e:
        print(f"🔍 DEBUG - Upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@files_bp.route('/delete_file/<int:message_id>', methods=['DELETE'])
def delete_file(message_id):
    """Delete a file message"""
    from flask import session

    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    message = Message.query.get_or_404(message_id)

    # Check if user owns this message
    if message.sender_id != user_id:
        return jsonify({'error': 'Not authorized'}), 403

    try:
        # Delete the physical file if it exists
        if message.file_path:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            base_upload_dir = os.path.join(os.path.dirname(current_dir), 'uploads')
            file_path = os.path.join(base_upload_dir, message.file_path)
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"🔍 DEBUG - Deleted file: {file_path}")

        # Delete the message
        db.session.delete(message)
        db.session.commit()

        return jsonify({'success': True, 'message': 'File deleted successfully'})

    except Exception as e:
        print(f"🔍 DEBUG - Delete error: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@files_bp.route('/file_info/<int:message_id>')
def file_info(message_id):
    """Get information about a file"""
    message = Message.query.get_or_404(message_id)

    if not message.has_attachment:
        return jsonify({'error': 'Message has no attachment'}), 404

    file_url = url_for('files.serve_file', filename=message.file_path, _external=False)

    return jsonify({
        'id': message.id,
        'file_name': message.file_name,
        'file_type': message.file_type,
        'file_size': message.file_size,
        'formatted_size': format_file_size(message.file_size),
        'file_url': file_url,
        'uploaded_at': message.timestamp.isoformat(),
        'sender_id': message.sender_id,
        'receiver_id': message.receiver_id
    })


@files_bp.route('/test_uploads')
def test_uploads():
    """Test if uploads directory is accessible"""
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        base_upload_dir = os.path.join(os.path.dirname(current_dir), 'uploads')

        result = {
            'current_dir': current_dir,
            'base_upload_dir': base_upload_dir,
            'uploads_exists': os.path.exists(base_upload_dir),
            'is_directory': os.path.isdir(base_upload_dir) if os.path.exists(base_upload_dir) else False,
            'permissions': oct(os.stat(base_upload_dir).st_mode)[-3:] if os.path.exists(base_upload_dir) else None,
            'files': []
        }

        if os.path.exists(base_upload_dir):
            for root, dirs, files in os.walk(base_upload_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, base_upload_dir)

                    # Generate URLs for testing
                    file_url = url_for('files.serve_file', filename=rel_path, _external=False)
                    absolute_url = url_for('files.serve_file', filename=rel_path, _external=True)

                    result['files'].append({
                        'filename': file,
                        'relative_path': rel_path,
                        'full_path': full_path,
                        'size': os.path.getsize(full_path),
                        'url_relative': file_url,
                        'url_absolute': absolute_url,
                        'url_direct': f'/files/uploads/{rel_path}'
                    })

        print(f"🔍 DEBUG - Test uploads result: {result}")
        return jsonify(result)
    except Exception as e:
        print(f"🔍 DEBUG - Test uploads error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@files_bp.route('/debug_url/<path:filename>')
def debug_url(filename):
    """Debug endpoint to test URL generation"""
    try:
        relative_url = url_for('files.serve_file', filename=filename, _external=False)
        absolute_url = url_for('files.serve_file', filename=filename, _external=True)

        return jsonify({
            'filename': filename,
            'relative_url': relative_url,
            'absolute_url': absolute_url,
            'request_url': request.url,
            'request_host': request.host,
            'request_root': request.url_root,
            'blueprint_name': files_bp.name,
            'endpoint': 'files.serve_file'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
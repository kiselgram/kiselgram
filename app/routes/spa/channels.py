import secrets
import os
from datetime import datetime
from flask import Blueprint, request, jsonify

from app import db
from app.models import User, Channel, ChannelSubscriber, Message, BlockedUser
from app.utils.helpers import get_current_user_id, get_current_user, message_to_dict

spa_channels_bp = Blueprint('spa_channels', __name__, url_prefix='/api')


# ==================== ENDPOINTS ====================

@spa_channels_bp.route('/channels/create', methods=['POST'])
def create_channel():
    """
    Create a new channel. Accepts JSON or multipart form data (with optional avatar).
    """
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    if request.is_json:
        data = request.get_json()
        name = data.get('name', '').strip()
        description = data.get('description', '')
        is_public = data.get('is_public', True)
    else:
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '')
        is_public = request.form.get('is_public', 'true').lower() == 'true'

    if not name or len(name) < 3:
        return jsonify({'success': False, 'error': 'Channel name must be at least 3 characters'}), 400

    invite_link = secrets.token_urlsafe(16)
    new_channel = Channel(
        name=name,
        description=description,
        owner_id=current_user_id,
        is_public=is_public,
        invite_link=invite_link,
        created_at=datetime.utcnow()
    )
    db.session.add(new_channel)
    db.session.flush()

    # Handle avatar upload (if any)
    if 'avatar' in request.files:
        file = request.files['avatar']
        if file and file.filename:
            try:
                from PIL import Image
                ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
                filename = f"channel_{new_channel.id}_{secrets.token_urlsafe(8)}.{ext}"
                upload_dir = os.path.join('uploads', 'channels')
                os.makedirs(upload_dir, exist_ok=True)
                file_path = os.path.join(upload_dir, filename)
                img = Image.open(file)
                img.thumbnail((200, 200))
                img.save(file_path)
                new_channel.avatar_url = f"/uploads/channels/{filename}"
            except:
                ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
                filename = f"channel_{new_channel.id}_{secrets.token_urlsafe(8)}.{ext}"
                upload_dir = os.path.join('uploads', 'channels')
                os.makedirs(upload_dir, exist_ok=True)
                file_path = os.path.join(upload_dir, filename)
                file.save(file_path)
                new_channel.avatar_url = f"/uploads/channels/{filename}"

    # Creator automatically subscribes
    db.session.add(ChannelSubscriber(user_id=current_user_id, channel_id=new_channel.id))
    db.session.commit()

    return jsonify({
        'success': True,
        'channel': {
            'id': new_channel.id,
            'name': new_channel.name,
            'avatar_url': new_channel.avatar_url,
            'invite_link': new_channel.invite_link
        }
    })


@spa_channels_bp.route('/channels/<int:channel_id>', methods=['GET'])
def get_channel(channel_id):
    """
    Get channel details, subscriber count, and current user's subscription status.
    """
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    channel = Channel.query.get(channel_id)
    if not channel:
        return jsonify({'success': False, 'error': 'Channel not found'}), 404

    subscription = ChannelSubscriber.query.filter_by(user_id=current_user_id, channel_id=channel_id).first()
    if not subscription:
        # If channel is public, still show basic info
        pass
    else:
        # Subscribed – allow full info
        pass

    subscriber_count = ChannelSubscriber.query.filter_by(channel_id=channel_id).count()
    is_owner = channel.owner_id == current_user_id

    return jsonify({
        'success': True,
        'channel': {
            'id': channel.id,
            'name': channel.name,
            'description': channel.description,
            'avatar_url': channel.avatar_url,
            'is_public': channel.is_public,
            'invite_link': channel.invite_link,
            'owner_id': channel.owner_id,
            'subscriber_count': subscriber_count,
        },
        'is_subscribed': subscription is not None,
        'is_owner': is_owner,
        'can_post': is_owner or (subscription is not None)  # owner can always post; subscribers can post if admin (to be refined later)
    })


@spa_channels_bp.route('/channel_messages/<int:channel_id>', methods=['GET'])
def get_channel_messages(channel_id):
    """
    Retrieve messages for a channel. Only subscribers can view.
    """
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    subscription = ChannelSubscriber.query.filter_by(user_id=current_user_id, channel_id=channel_id).first()
    channel = Channel.query.get(channel_id)
    if not subscription and (not channel or channel.owner_id != current_user_id):
        return jsonify({'success': False, 'error': 'Not subscribed'}), 403

    after_id = request.args.get('after', 0, type=int)
    limit = request.args.get('limit', 50, type=int)

    messages = Message.query.filter_by(channel_id=channel_id) \
        .filter(Message.id > after_id) \
        .order_by(Message.timestamp.asc()) \
        .limit(limit).all()

    from app.routes.spa.chat import message_to_dict
    result = [message_to_dict(msg, current_user_id) for msg in messages]
    return jsonify({'success': True, 'messages': result})


@spa_channels_bp.route('/send_channel_message', methods=['POST'])
def send_channel_message():
    """
    Post a message to a channel (only owner can post, or admins if implemented).
    """
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    if request.is_json:
        data = request.get_json()
        channel_id = data.get('channel_id')
        content = data.get('content', '').strip()
    else:
        channel_id = request.form.get('channel_id')
        content = request.form.get('content', '').strip()

    if not channel_id or not content:
        return jsonify({'success': False, 'error': 'channel_id and content are required'}), 400

    channel = Channel.query.get(int(channel_id))
    if not channel:
        return jsonify({'success': False, 'error': 'Channel not found'}), 404

    # For now, only owner can post
    if channel.owner_id != current_user_id:
        return jsonify({'success': False, 'error': 'Only the owner can post'}), 403

    new_message = Message(
        sender_id=current_user_id,
        channel_id=channel.id,
        receiver_id=current_user_id,  # dummy
        content=content,
        timestamp=datetime.utcnow()
    )
    db.session.add(new_message)
    db.session.commit()

    from app.routes.spa.chat import message_to_dict
    return jsonify({'success': True, 'message': message_to_dict(new_message, current_user_id)})


@spa_channels_bp.route('/channels/<int:channel_id>/subscribe', methods=['POST'])
def subscribe_channel(channel_id):
    """Subscribe to a channel."""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    existing = ChannelSubscriber.query.filter_by(user_id=current_user_id, channel_id=channel_id).first()
    if existing:
        return jsonify({'success': True, 'already_subscribed': True})

    db.session.add(ChannelSubscriber(user_id=current_user_id, channel_id=channel_id))
    db.session.commit()
    return jsonify({'success': True, 'subscribed': True})


@spa_channels_bp.route('/channels/<int:channel_id>/unsubscribe', methods=['POST'])
def unsubscribe_channel(channel_id):
    """Unsubscribe from a channel (owner cannot unsubscribe)."""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    channel = Channel.query.get(channel_id)
    if channel and channel.owner_id == current_user_id:
        return jsonify({'success': False, 'error': 'Owner cannot unsubscribe'}), 400

    ChannelSubscriber.query.filter_by(user_id=current_user_id, channel_id=channel_id).delete()
    db.session.commit()
    return jsonify({'success': True, 'subscribed': False})


@spa_channels_bp.route('/channels/<int:channel_id>/update', methods=['POST'])
def update_channel(channel_id):
    """Update channel name, description, or public/private setting. Owner only."""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    channel = Channel.query.get(channel_id)
    if not channel or channel.owner_id != current_user_id:
        return jsonify({'success': False, 'error': 'Insufficient permissions'}), 403

    data = request.get_json() or {}
    if 'name' in data:
        channel.name = data['name']
    if 'description' in data:
        channel.description = data['description']
    if 'is_public' in data:
        channel.is_public = data['is_public']

    db.session.commit()
    return jsonify({'success': True})


# ==================== CHANNEL ADMINS (NyEXGRAM feature) ====================

@spa_channels_bp.route('/channels/<int:channel_id>/admins', methods=['GET'])
def get_channel_admins(channel_id):
    """List all admins of a channel."""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    # For now, return only the owner as admin (until ChannelAdmin model is added)
    channel = Channel.query.get(channel_id)
    if not channel:
        return jsonify({'success': False, 'error': 'Channel not found'}), 404

    owner = User.query.get(channel.owner_id)
    admins = [{
        'user_id': owner.id,
        'username': owner.username,
        'display_name': owner.display_name or owner.username,
        'avatar_url': owner.avatar_url,
        'can_post': True,
        'can_edit': True,
        'can_delete': True,
        'can_add_admins': True
    }]

    return jsonify({'success': True, 'admins': admins})


@spa_channels_bp.route('/channels/<int:channel_id>/admins', methods=['POST'])
def add_channel_admin(channel_id):
    """Add a user as admin (owner only)."""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    channel = Channel.query.get(channel_id)
    if not channel or channel.owner_id != current_user_id:
        return jsonify({'success': False, 'error': 'Insufficient permissions'}), 403

    data = request.get_json() or {}
    user_id = data.get('user_id')
    permissions = data.get('permissions', {})

    # TODO: add logic to insert into a ChannelAdmin table
    return jsonify({'success': True})


@spa_channels_bp.route('/channels/<int:channel_id>/admins/<int:user_id>', methods=['DELETE'])
def remove_channel_admin(channel_id, user_id):
    """Remove an admin (owner only)."""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    channel = Channel.query.get(channel_id)
    if not channel or channel.owner_id != current_user_id:
        return jsonify({'success': False, 'error': 'Insufficient permissions'}), 403

    # TODO: remove from ChannelAdmin table
    return jsonify({'success': True})


@spa_channels_bp.route('/channels/<int:channel_id>/delete', methods=['POST'])
def delete_channel(channel_id):
    """Delete a channel (owner only)."""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    channel = Channel.query.get(channel_id)
    if not channel or channel.owner_id != current_user_id:
        return jsonify({'success': False, 'error': 'Insufficient permissions'}), 403

    # Delete all related data (messages, subscribers, etc.) manually or via cascade
    Message.query.filter_by(channel_id=channel_id).delete()
    ChannelSubscriber.query.filter_by(channel_id=channel_id).delete()
    db.session.delete(channel)
    db.session.commit()

    return jsonify({'success': True})
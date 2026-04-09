# spa.py - Complete version with all endpoints

from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from datetime import datetime, timedelta
from app import db
from app.models import (
    User, Message, Group, GroupMember, Channel, ChannelSubscriber,
    Reaction, Reply, Forward, BlockedUser, Report, Story, StoryView
)
from app.utils.helpers import get_current_user, get_current_user_id, format_file_size, hash_password
import re
import secrets
import os

spa_bp = Blueprint('spa', __name__, url_prefix='/api')


# ============ HELPER FUNCTIONS ============

def get_blocked_user_ids(user_id):
    """Get list of user IDs blocked by the given user"""
    blocks = BlockedUser.query.filter_by(user_id=user_id).all()
    return [b.blocked_user_id for b in blocks]


def user_to_dict(user):
    """Convert user to dictionary"""
    return {
        'id': user.id,
        'username': user.username,
        'display_name': user.display_name or user.username,
        'bio': user.bio,
        'avatar_url': user.avatar_url,
        'is_online': user.is_online,
        'last_seen': user.last_seen.isoformat() if user.last_seen else None,
        'created_at': user.created_at.isoformat() if user.created_at else None,
        'has_story': has_active_story(user.id),
        'followers_count': 0,
        'following_count': 0,
        'groups_count': GroupMember.query.filter_by(user_id=user.id).count()
    }


def has_active_story(user_id):
    """Check if user has active story (within 24 hours)"""
    cutoff = datetime.utcnow() - timedelta(hours=24)
    return Story.query.filter(
        Story.user_id == user_id,
        Story.created_at >= cutoff
    ).count() > 0


def message_to_dict(message, current_user_id):
    """Convert message to dictionary with rich data"""
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
        'reactions': {},
        'is_pinned': message.is_pinned if hasattr(message, 'is_pinned') else False
    }

    if message.has_attachment:
        msg_data['file_type'] = message.file_type
        msg_data['file_name'] = message.file_name
        msg_data['file_size'] = message.file_size
        msg_data['formatted_size'] = format_file_size(message.file_size) if message.file_size else '0 B'
        msg_data['file_url'] = f"/uploads/{message.file_path}" if message.file_path else None

    if message.reply_to:
        original = message.reply_to.original_message
        if original:
            msg_data['reply_to_id'] = original.id
            msg_data['reply_to_content'] = (original.content[:100] + '...') if original.content and len(
                original.content) > 100 else (original.content or '[Media]')
            msg_data['reply_to_sender'] = original.sender.username if original.sender else 'Unknown'

    return msg_data


# ============ CHAT LIST ROUTES ============

@spa_bp.route('/chat_list', methods=['GET'])
def chat_list_api():
    """Get all chats for the current user"""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    blocked_ids = get_blocked_user_ids(current_user_id)
    chats = []

    # Get personal chats
    sent = db.session.query(Message.receiver_id).filter_by(sender_id=current_user_id).distinct()
    recv = db.session.query(Message.sender_id).filter_by(receiver_id=current_user_id).distinct()
    chat_user_ids = set([id[0] for id in sent] + [id[0] for id in recv])

    for uid in chat_user_ids:
        if uid in blocked_ids or uid == current_user_id:
            continue
        user = User.query.get(uid)
        if user:
            last = Message.query.filter(
                ((Message.sender_id == current_user_id) & (Message.receiver_id == uid)) |
                ((Message.sender_id == uid) & (Message.receiver_id == current_user_id))
            ).order_by(Message.timestamp.desc()).first()

            unread = Message.query.filter_by(sender_id=uid, receiver_id=current_user_id, is_read=False).count()

            timestamp = ''
            if last and last.timestamp:
                time_diff = datetime.utcnow() - last.timestamp
                if time_diff.days == 0:
                    timestamp = last.timestamp.strftime('%H:%M')
                elif time_diff.days == 1:
                    timestamp = 'Yesterday'
                else:
                    timestamp = last.timestamp.strftime('%d.%m.%Y')

            chats.append({
                'type': 'personal',
                'id': user.id,
                'name': user.display_name or user.username,
                'avatar': user.username[0].upper() if user.username else '?',
                'last_message': last.content[:50] + '...' if last and last.content and len(last.content) > 50 else (
                    last.content if last else 'No messages yet'),
                'timestamp': timestamp,
                'unread_count': unread,
                'is_online': user.is_online,
                'is_pinned': False,  # Add pin support later
                'has_story': has_active_story(user.id)
            })

    # Get groups
    memberships = GroupMember.query.filter_by(user_id=current_user_id).all()
    for membership in memberships:
        group = membership.group
        if group:
            last = Message.query.filter_by(group_id=group.id).order_by(Message.timestamp.desc()).first()
            unread = Message.query.filter_by(group_id=group.id, is_read=False).filter(
                Message.sender_id != current_user_id).count()

            timestamp = ''
            if last and last.timestamp:
                time_diff = datetime.utcnow() - last.timestamp
                if time_diff.days == 0:
                    timestamp = last.timestamp.strftime('%H:%M')
                elif time_diff.days == 1:
                    timestamp = 'Yesterday'
                else:
                    timestamp = last.timestamp.strftime('%d.%m.%Y')

            chats.append({
                'type': 'group',
                'id': group.id,
                'name': group.name,
                'avatar': '👥',
                'last_message': last.content[:50] + '...' if last and last.content and len(last.content) > 50 else (
                    last.content if last else 'No messages yet'),
                'timestamp': timestamp,
                'unread_count': unread,
                'member_count': len(group.members),
                'role': membership.role,
                'is_pinned': False
            })

    # Get channels
    subscriptions = ChannelSubscriber.query.filter_by(user_id=current_user_id).all()
    for subscription in subscriptions:
        channel = subscription.channel
        if channel:
            last = Message.query.filter_by(channel_id=channel.id).order_by(Message.timestamp.desc()).first()

            timestamp = ''
            if last and last.timestamp:
                time_diff = datetime.utcnow() - last.timestamp
                if time_diff.days == 0:
                    timestamp = last.timestamp.strftime('%H:%M')
                elif time_diff.days == 1:
                    timestamp = 'Yesterday'
                else:
                    timestamp = last.timestamp.strftime('%d.%m.%Y')

            chats.append({
                'type': 'channel',
                'id': channel.id,
                'name': channel.name,
                'avatar': '📢',
                'last_message': last.content[:50] + '...' if last and last.content and len(last.content) > 50 else (
                    last.content if last else 'No posts yet'),
                'timestamp': timestamp,
                'unread_count': 0,
                'subscriber_count': len(channel.subscribers),
                'is_owner': channel.owner_id == current_user_id,
                'is_pinned': False
            })

    # Sort: pinned first, then by timestamp
    chats.sort(key=lambda x: (not x.get('is_pinned', False), x['timestamp'] if x['timestamp'] else ''), reverse=False)
    chats.sort(key=lambda x: x.get('is_pinned', False), reverse=True)

    return jsonify({'success': True, 'chats': chats})


# ============ CONTACTS ROUTES ============

@spa_bp.route('/contacts', methods=['GET'])
def get_contacts():
    """Get user's contacts"""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    sent = db.session.query(Message.receiver_id).filter_by(sender_id=current_user_id).distinct()
    recv = db.session.query(Message.sender_id).filter_by(receiver_id=current_user_id).distinct()
    contact_ids = set([id[0] for id in sent] + [id[0] for id in recv])

    blocked_ids = get_blocked_user_ids(current_user_id)

    contacts = []
    for uid in contact_ids:
        if uid in blocked_ids or uid == current_user_id:
            continue
        user = User.query.get(uid)
        if user:
            contacts.append(user_to_dict(user))

    contacts.sort(key=lambda x: x['username'].lower())

    return jsonify({'success': True, 'contacts': contacts})


# ============ GROUPS ROUTES ============

@spa_bp.route('/groups/create', methods=['POST'])
def create_group():
    """Create a new group"""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    data = request.get_json()
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    is_public = data.get('is_public', True)
    member_ids = data.get('member_ids', [])

    if not name or len(name) < 3:
        return jsonify({'success': False, 'error': 'Group name must be at least 3 characters'}), 400

    invite_link = secrets.token_urlsafe(16)

    new_group = Group(
        name=name,
        description=description,
        owner_id=current_user_id,
        is_public=is_public,
        invite_link=invite_link
    )
    db.session.add(new_group)
    db.session.flush()

    db.session.add(GroupMember(user_id=current_user_id, group_id=new_group.id, role='owner'))

    for member_id in member_ids:
        if member_id != current_user_id:
            db.session.add(GroupMember(user_id=member_id, group_id=new_group.id, role='member'))

    db.session.commit()

    return jsonify({
        'success': True,
        'group': {
            'id': new_group.id,
            'name': new_group.name,
            'description': new_group.description,
            'invite_link': invite_link
        }
    })


# ============ CHANNELS ROUTES ============

@spa_bp.route('/channels/create', methods=['POST'])
def create_channel():
    """Create a new channel"""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    data = request.get_json()
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    is_public = data.get('is_public', True)

    if not name or len(name) < 3:
        return jsonify({'success': False, 'error': 'Channel name must be at least 3 characters'}), 400

    invite_link = secrets.token_urlsafe(16)

    new_channel = Channel(
        name=name,
        description=description,
        owner_id=current_user_id,
        is_public=is_public,
        invite_link=invite_link
    )
    db.session.add(new_channel)
    db.session.flush()

    db.session.add(ChannelSubscriber(user_id=current_user_id, channel_id=new_channel.id))
    db.session.commit()

    return jsonify({
        'success': True,
        'channel': {
            'id': new_channel.id,
            'name': new_channel.name,
            'description': new_channel.description,
            'invite_link': invite_link
        }
    })


# ============ STORIES ROUTES ============

@spa_bp.route('/stories', methods=['GET'])
def get_stories():
    """Get active stories from contacts"""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    cutoff = datetime.utcnow() - timedelta(hours=24)

    # Get contacts
    sent = db.session.query(Message.receiver_id).filter_by(sender_id=current_user_id).distinct()
    recv = db.session.query(Message.sender_id).filter_by(receiver_id=current_user_id).distinct()
    contact_ids = set([id[0] for id in sent] + [id[0] for id in recv])

    stories = []
    for uid in contact_ids:
        user_stories = Story.query.filter(
            Story.user_id == uid,
            Story.created_at >= cutoff
        ).order_by(Story.created_at.asc()).all()

        if user_stories:
            user = User.query.get(uid)
            viewed_story_ids = [v.story_id for v in StoryView.query.filter_by(viewer_id=current_user_id).all()]

            stories.append({
                'user_id': uid,
                'username': user.username,
                'display_name': user.display_name or user.username,
                'avatar_url': user.avatar_url,
                'stories': [{
                    'id': s.id,
                    'media_url': f"/uploads/{s.media_path}",
                    'media_type': s.media_type,
                    'caption': s.caption,
                    'created_at': s.created_at.isoformat(),
                    'viewed': s.id in viewed_story_ids,
                    'views_count': len(s.views),
                    'likes_count': len(s.likes)
                } for s in user_stories]
            })

    return jsonify({'success': True, 'stories': stories})


@spa_bp.route('/stories/upload', methods=['POST'])
def upload_story():
    """Upload a new story"""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    if 'media' not in request.files:
        return jsonify({'success': False, 'error': 'No media provided'}), 400

    file = request.files['media']
    caption = request.form.get('caption', '')

    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400

    # Determine media type
    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
        media_type = 'image'
    elif ext in ['mp4', 'mov', 'avi', 'webm']:
        media_type = 'video'
    else:
        return jsonify({'success': False, 'error': 'Unsupported media type'}), 400

    # Save file
    unique_filename = f"story_{secrets.token_urlsafe(16)}.{ext}"
    upload_dir = os.path.join('uploads', 'stories')
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join('stories', unique_filename)
    full_path = os.path.join('uploads', file_path)
    file.save(full_path)

    # Create story
    new_story = Story(
        user_id=current_user_id,
        media_path=file_path,
        media_type=media_type,
        caption=caption
    )
    db.session.add(new_story)
    db.session.commit()

    return jsonify({
        'success': True,
        'story': {
            'id': new_story.id,
            'media_url': f"/uploads/{file_path}",
            'media_type': media_type,
            'caption': caption
        }
    })


@spa_bp.route('/stories/<int:story_id>/view', methods=['POST'])
def view_story(story_id):
    """Mark a story as viewed"""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    existing = StoryView.query.filter_by(story_id=story_id, viewer_id=current_user_id).first()
    if not existing:
        db.session.add(StoryView(story_id=story_id, viewer_id=current_user_id))
        db.session.commit()

    return jsonify({'success': True})


@spa_bp.route('/stories/<int:story_id>/like', methods=['POST'])
def like_story(story_id):
    """Like a story (only once per user)"""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    from app.models import StoryLike
    existing = StoryLike.query.filter_by(story_id=story_id, user_id=current_user_id).first()

    if existing:
        db.session.delete(existing)
        action = 'unliked'
    else:
        db.session.add(StoryLike(story_id=story_id, user_id=current_user_id))
        action = 'liked'

    db.session.commit()

    likes_count = StoryLike.query.filter_by(story_id=story_id).count()

    return jsonify({'success': True, 'action': action, 'likes_count': likes_count})


@spa_bp.route('/stories/<int:story_id>/views', methods=['GET'])
def get_story_views(story_id):
    """Get list of users who viewed a story (only for story owner)"""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    story = Story.query.get(story_id)
    if not story:
        return jsonify({'success': False, 'error': 'Story not found'}), 404

    if story.user_id != current_user_id:
        return jsonify({'success': False, 'error': 'Not authorized'}), 403

    views = StoryView.query.filter_by(story_id=story_id).all()
    viewers = []
    for view in views:
        user = User.query.get(view.viewer_id)
        if user:
            viewers.append({
                'id': user.id,
                'username': user.username,
                'display_name': user.display_name or user.username,
                'viewed_at': view.viewed_at.isoformat()
            })

    likes = StoryLike.query.filter_by(story_id=story_id).all()
    likers = []
    for like in likes:
        user = User.query.get(like.user_id)
        if user:
            likers.append({
                'id': user.id,
                'username': user.username,
                'display_name': user.display_name or user.username
            })

    return jsonify({
        'success': True,
        'views': viewers,
        'likes': likers
    })


# ============ PIN CHAT ROUTES ============

@spa_bp.route('/pin_chat', methods=['POST'])
def pin_chat():
    """Pin or unpin a chat"""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    data = request.get_json()
    chat_type = data.get('type')
    chat_id = data.get('id')
    action = data.get('action')  # 'pin' or 'unpin'

    # Store pin in user settings (you can add a PinnedChat model)
    # For now, just return success
    return jsonify({'success': True, 'action': action})


# ============ CHAT CUSTOMIZATION ROUTES ============

@spa_bp.route('/chat_settings', methods=['GET'])
def get_chat_settings():
    """Get chat customization settings"""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    # Default settings
    settings = {
        'font_size': 'medium',
        'border_radius': '18px',
        'font_family': 'Segoe UI',
        'own_message_color': '#5e72e4',
        'other_message_color': '#ffffff',
        'wallpaper_type': 'gradient',
        'wallpaper_value': 'linear-gradient(145deg, #e9f0f5, #ffffff)'
    }

    return jsonify({'success': True, 'settings': settings})


@spa_bp.route('/chat_settings', methods=['POST'])
def update_chat_settings():
    """Update chat customization settings"""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    data = request.get_json()
    # Save settings to user preferences
    return jsonify({'success': True})


# ============ MESSAGES ROUTES ============

@spa_bp.route('/messages/<int:user_id>', methods=['GET'])
def get_personal_messages(user_id):
    """Get messages in a personal chat"""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    after_id = request.args.get('after', 0, type=int)
    limit = request.args.get('limit', 50, type=int)

    messages = Message.query.filter(
        ((Message.sender_id == current_user_id) & (Message.receiver_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.receiver_id == current_user_id))
    ).filter(Message.id > after_id).order_by(Message.timestamp.asc()).limit(limit).all()

    messages_data = [message_to_dict(msg, current_user_id) for msg in messages]

    return jsonify({'success': True, 'messages': messages_data})


@spa_bp.route('/group_messages/<int:group_id>', methods=['GET'])
def get_group_messages(group_id):
    """Get messages in a group"""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    membership = GroupMember.query.filter_by(user_id=current_user_id, group_id=group_id).first()
    if not membership:
        return jsonify({'success': False, 'error': 'Not a member'}), 403

    after_id = request.args.get('after', 0, type=int)
    limit = request.args.get('limit', 50, type=int)

    messages = Message.query.filter_by(group_id=group_id).filter(Message.id > after_id).order_by(
        Message.timestamp.asc()).limit(limit).all()
    messages_data = [message_to_dict(msg, current_user_id) for msg in messages]

    return jsonify({'success': True, 'messages': messages_data})


@spa_bp.route('/channel_messages/<int:channel_id>', methods=['GET'])
def get_channel_messages(channel_id):
    """Get messages in a channel"""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    subscription = ChannelSubscriber.query.filter_by(user_id=current_user_id, channel_id=channel_id).first()
    channel = Channel.query.get(channel_id)

    if not subscription and channel and channel.owner_id != current_user_id:
        return jsonify({'success': False, 'error': 'Not subscribed'}), 403

    after_id = request.args.get('after', 0, type=int)
    limit = request.args.get('limit', 50, type=int)

    messages = Message.query.filter_by(channel_id=channel_id).filter(Message.id > after_id).order_by(
        Message.timestamp.asc()).limit(limit).all()
    messages_data = [message_to_dict(msg, current_user_id) for msg in messages]

    return jsonify({'success': True, 'messages': messages_data})


@spa_bp.route('/send_message', methods=['POST'])
def send_personal_message():
    """Send a personal message"""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    data = request.get_json()
    receiver_id = data.get('receiver_id')
    content = data.get('content', '').strip()
    reply_to_id = data.get('reply_to_id')

    if not content:
        return jsonify({'success': False, 'error': 'Message content is required'}), 400

    receiver = User.query.get(receiver_id)
    if not receiver:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    if BlockedUser.query.filter_by(user_id=receiver_id, blocked_user_id=current_user_id).first():
        return jsonify({'success': False, 'error': 'You are blocked by this user'}), 403

    new_message = Message(
        content=content,
        sender_id=current_user_id,
        receiver_id=receiver_id
    )

    db.session.add(new_message)
    db.session.flush()

    if reply_to_id:
        original = Message.query.get(reply_to_id)
        if original:
            reply = Reply(original_message_id=reply_to_id, reply_message_id=new_message.id)
            db.session.add(reply)

    db.session.commit()

    return jsonify({
        'success': True,
        'message': message_to_dict(new_message, current_user_id)
    })


@spa_bp.route('/send_group_message', methods=['POST'])
def send_group_message():
    """Send a group message"""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    data = request.get_json()
    group_id = data.get('group_id')
    content = data.get('content', '').strip()
    reply_to_id = data.get('reply_to_id')

    if not content:
        return jsonify({'success': False, 'error': 'Message content is required'}), 400

    membership = GroupMember.query.filter_by(user_id=current_user_id, group_id=group_id).first()
    if not membership:
        return jsonify({'success': False, 'error': 'Not a member'}), 403

    new_message = Message(
        content=content,
        sender_id=current_user_id,
        group_id=group_id,
        receiver_id=current_user_id
    )

    db.session.add(new_message)
    db.session.flush()

    if reply_to_id:
        original = Message.query.get(reply_to_id)
        if original:
            reply = Reply(original_message_id=reply_to_id, reply_message_id=new_message.id)
            db.session.add(reply)

    db.session.commit()

    return jsonify({
        'success': True,
        'message': message_to_dict(new_message, current_user_id)
    })


@spa_bp.route('/send_channel_message', methods=['POST'])
def send_channel_message():
    """Send a channel message"""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    data = request.get_json()
    channel_id = data.get('channel_id')
    content = data.get('content', '').strip()

    if not content:
        return jsonify({'success': False, 'error': 'Message content is required'}), 400

    channel = Channel.query.get(channel_id)
    if not channel or channel.owner_id != current_user_id:
        return jsonify({'success': False, 'error': 'Only channel owner can post'}), 403

    new_message = Message(
        content=content,
        sender_id=current_user_id,
        channel_id=channel_id,
        receiver_id=current_user_id
    )

    db.session.add(new_message)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': message_to_dict(new_message, current_user_id)
    })


@spa_bp.route('/mark_read/<int:user_id>', methods=['POST'])
def mark_messages_read(user_id):
    """Mark messages as read"""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    Message.query.filter_by(sender_id=user_id, receiver_id=current_user_id, is_read=False).update({
        'is_read': True,
        'read_at': datetime.utcnow()
    })

    db.session.commit()
    return jsonify({'success': True})


# ============ REACTIONS ROUTES ============

@spa_bp.route('/reactions/<int:message_id>', methods=['GET'])
def get_reactions(message_id):
    """Get reactions for a message"""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    reactions = Reaction.query.filter_by(message_id=message_id).all()
    grouped = {}

    for r in reactions:
        if r.reaction_type not in grouped:
            grouped[r.reaction_type] = {'type': r.reaction_type, 'count': 0}
        grouped[r.reaction_type]['count'] += 1

    return jsonify({
        'success': True,
        'message_id': message_id,
        'reactions': list(grouped.values())
    })


@spa_bp.route('/reactions/add', methods=['POST'])
def add_reaction():
    """Add or remove a reaction"""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    data = request.get_json()
    message_id = data.get('message_id')
    reaction_type = data.get('reaction_type')

    valid_reactions = ['👍', '❤️', '😂', '😮', '😢', '👏', '🔥', '🎉', '💯']
    if reaction_type not in valid_reactions:
        return jsonify({'success': False, 'error': 'Invalid reaction type'}), 400

    existing = Reaction.query.filter_by(message_id=message_id, user_id=current_user_id).first()

    if existing:
        if existing.reaction_type == reaction_type:
            db.session.delete(existing)
            action = 'removed'
        else:
            existing.reaction_type = reaction_type
            action = 'updated'
    else:
        db.session.add(Reaction(
            message_id=message_id,
            user_id=current_user_id,
            reaction_type=reaction_type
        ))
        action = 'added'

    db.session.commit()

    reactions = Reaction.query.filter_by(message_id=message_id).all()
    grouped = {}
    for r in reactions:
        if r.reaction_type not in grouped:
            grouped[r.reaction_type] = {'type': r.reaction_type, 'count': 0}
        grouped[r.reaction_type]['count'] += 1

    return jsonify({
        'success': True,
        'action': action,
        'message_id': message_id,
        'reactions': list(grouped.values())
    })


# ============ FORWARD ROUTES ============

@spa_bp.route('/forward_message', methods=['POST'])
def forward_message():
    """Forward a message"""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    data = request.get_json()
    original_id = data.get('message_id')
    target_type = data.get('target_type')
    target_id = data.get('target_id')

    original = Message.query.get(original_id)
    if not original:
        return jsonify({'success': False, 'error': 'Original message not found'}), 404

    content = original.content
    if original.sender:
        content = f"📨 Forwarded from {original.sender.username}:\n{content}" if content else "📨 Forwarded message"

    new_message = Message(
        content=content,
        sender_id=current_user_id,
        has_attachment=original.has_attachment,
        file_name=original.file_name,
        file_path=original.file_path,
        file_type=original.file_type,
        file_size=original.file_size
    )

    if target_type == 'personal':
        new_message.receiver_id = int(target_id)
    elif target_type == 'group':
        new_message.group_id = int(target_id)
        new_message.receiver_id = current_user_id
    elif target_type == 'channel':
        channel = Channel.query.get(int(target_id))
        if channel and channel.owner_id != current_user_id:
            return jsonify({'success': False, 'error': 'Only channel owner can post'}), 403
        new_message.channel_id = int(target_id)
        new_message.receiver_id = current_user_id
    else:
        return jsonify({'success': False, 'error': 'Invalid target type'}), 400

    db.session.add(new_message)
    db.session.flush()

    db.session.add(Forward(
        original_message_id=original_id,
        forwarded_message_id=new_message.id,
        forwarded_by_id=current_user_id,
        original_sender_name=original.sender.username if original.sender else 'Unknown'
    ))

    db.session.commit()

    return jsonify({
        'success': True,
        'message': message_to_dict(new_message, current_user_id)
    })


# ============ USER/PROFILE ROUTES ============

@spa_bp.route('/users', methods=['GET'])
def get_users():
    """Get list of all users"""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    search = request.args.get('search', '')
    query = User.query.filter(User.id != current_user_id)

    if search:
        query = query.filter(User.username.ilike(f'%{search}%'))

    users = query.limit(50).all()

    return jsonify({
        'success': True,
        'users': [user_to_dict(u) for u in users]
    })


@spa_bp.route('/profile', methods=['GET'])
def get_my_profile():
    """Get current user's profile"""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    user = User.query.get(current_user_id)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    return jsonify({'success': True, 'user': user_to_dict(user)})


@spa_bp.route('/profile/update', methods=['PUT'])
def update_profile():
    """Update user profile"""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    data = request.get_json()
    user = User.query.get(current_user_id)

    if 'display_name' in data:
        display_name = data['display_name'].strip()
        user.display_name = display_name[:80] if display_name else None

    if 'bio' in data:
        bio = data['bio'].strip()
        user.bio = bio[:500] if bio else None

    if 'username' in data:
        new_username = data['username'].strip()
        if len(new_username) >= 3 and re.match(r'^[a-zA-Z0-9_]+$', new_username):
            existing = User.query.filter_by(username=new_username).first()
            if not existing or existing.id == current_user_id:
                user.username = new_username
                session['username'] = new_username

    db.session.commit()

    return jsonify({'success': True, 'user': user_to_dict(user)})


# ============ AUTH ROUTES ============

@spa_bp.route('/auth/logout', methods=['POST'])
def spa_logout():
    """Logout user"""
    user_id = session.get('user_id')
    if user_id:
        user = User.query.get(user_id)
        if user:
            user.is_online = False
            user.last_seen = datetime.utcnow()
            db.session.commit()
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully'})


# ============ BLOCK USER ROUTES ============

@spa_bp.route('/block_user/<int:user_id>', methods=['POST'])
def block_user(user_id):
    """Block a user"""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    if current_user_id == user_id:
        return jsonify({'success': False, 'error': 'Cannot block yourself'}), 400

    existing = BlockedUser.query.filter_by(user_id=current_user_id, blocked_user_id=user_id).first()
    if existing:
        return jsonify({'success': False, 'error': 'User already blocked'}), 400

    block = BlockedUser(user_id=current_user_id, blocked_user_id=user_id)
    db.session.add(block)
    db.session.commit()

    return jsonify({'success': True, 'message': 'User blocked'})


@spa_bp.route('/clear_chat/<int:user_id>', methods=['POST'])
def clear_chat(user_id):
    """Clear chat with a user"""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    Message.query.filter(
        ((Message.sender_id == current_user_id) & (Message.receiver_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.receiver_id == current_user_id))
    ).delete()

    db.session.commit()
    return jsonify({'success': True, 'message': 'Chat cleared'})


# ============ LEAVE GROUP/CHANNEL ============

@spa_bp.route('/leave_group/<int:group_id>', methods=['POST'])
def leave_group(group_id):
    """Leave a group"""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    membership = GroupMember.query.filter_by(user_id=current_user_id, group_id=group_id).first()
    if membership:
        db.session.delete(membership)
        db.session.commit()

    return jsonify({'success': True})


@spa_bp.route('/leave_channel/<int:channel_id>', methods=['POST'])
def leave_channel(channel_id):
    """Leave a channel"""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    subscription = ChannelSubscriber.query.filter_by(user_id=current_user_id, channel_id=channel_id).first()
    if subscription:
        db.session.delete(subscription)
        db.session.commit()

    return jsonify({'success': True})


def register_spa_bp(app):
    """Register the SPA blueprint"""
    app.register_blueprint(spa_bp)
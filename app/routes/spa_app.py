from flask import Blueprint, request, jsonify, session
from datetime import datetime
from app import db
from app.models import (
    User, Message, Group, GroupMember, Channel, ChannelSubscriber,
    Reaction, Reply, Forward, BlockedUser, Report
)
from app.utils.helpers import get_current_user, get_current_user_id, format_file_size, hash_password
import re

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
        'followers_count': 0,  # Add actual counts if you have followers
        'following_count': 0,
        'groups_count': GroupMember.query.filter_by(user_id=user.id).count()
    }


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
        'reactions': {}
    }

    # Add attachment info if present
    if message.has_attachment:
        msg_data['file_type'] = message.file_type
        msg_data['file_name'] = message.file_name
        msg_data['file_size'] = message.file_size
        msg_data['formatted_size'] = format_file_size(message.file_size) if message.file_size else '0 B'
        msg_data['file_url'] = f"/uploads/{message.file_path}" if message.file_path else None
        if message.file_type == 'image' and message.thumbnail_path:
            msg_data['thumbnail_url'] = f"/uploads/{message.thumbnail_path}"

    # Add reply info
    if message.reply_to:
        original = message.reply_to.original_message
        if original:
            msg_data['reply_to_id'] = original.id
            msg_data['reply_to_content'] = (original.content[:100] + '...') if original.content and len(
                original.content) > 100 else (original.content or '[Media]')
            msg_data['reply_to_sender'] = original.sender.username if original.sender else 'Unknown'

    # Add forward info
    if message.forwards_from:
        original = message.forwards_from.original_message
        if original:
            msg_data['forwarded_from'] = original.sender.username if original.sender else 'Unknown'

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
                'last_message': last.content[:50] + '...' if last and last.content and len(last.content) > 50 else (last.content if last else 'No messages yet'),
                'timestamp': timestamp,
                'unread_count': unread,
                'is_online': user.is_online
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
                'last_message': last.content[:50] + '...' if last and last.content and len(last.content) > 50 else (last.content if last else 'No messages yet'),
                'timestamp': timestamp,
                'unread_count': unread,
                'member_count': len(group.members),
                'role': membership.role
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
                'last_message': last.content[:50] + '...' if last and last.content and len(last.content) > 50 else (last.content if last else 'No posts yet'),
                'timestamp': timestamp,
                'unread_count': 0,
                'subscriber_count': len(channel.subscribers),
                'is_owner': channel.owner_id == current_user_id
            })

    # Sort by timestamp (most recent first)
    chats.sort(key=lambda x: x['timestamp'] if x['timestamp'] else '', reverse=True)

    return jsonify({'success': True, 'chats': chats})


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

    # Check membership
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

    # Check subscription
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

    # Check if blocked
    if BlockedUser.query.filter_by(user_id=receiver_id, blocked_user_id=current_user_id).first():
        return jsonify({'success': False, 'error': 'You are blocked by this user'}), 403

    new_message = Message(
        content=content,
        sender_id=current_user_id,
        receiver_id=receiver_id
    )

    db.session.add(new_message)
    db.session.flush()

    # Add reply if present
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
        receiver_id=current_user_id  # Placeholder
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
    """Send a channel message (owner only)"""
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
    """Mark messages from a user as read"""
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
    reaction_list = []
    user_reaction = None

    for r in reactions:
        reaction_list.append({
            'type': r.reaction_type,
            'user_id': r.user_id,
            'username': r.user.username if r.user else 'Unknown'
        })
        if r.user_id == current_user_id:
            user_reaction = r.reaction_type

    # Group by reaction type
    grouped = {}
    for r in reaction_list:
        if r['type'] not in grouped:
            grouped[r['type']] = {'type': r['type'], 'count': 0, 'users': []}
        grouped[r['type']]['count'] += 1
        grouped[r['type']]['users'].append(r['username'])

    return jsonify({
        'success': True,
        'message_id': message_id,
        'reactions': list(grouped.values()),
        'user_reaction': user_reaction
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
            # Remove reaction
            db.session.delete(existing)
            action = 'removed'
        else:
            # Change reaction
            existing.reaction_type = reaction_type
            action = 'updated'
    else:
        # Add new reaction
        db.session.add(Reaction(
            message_id=message_id,
            user_id=current_user_id,
            reaction_type=reaction_type
        ))
        action = 'added'

    db.session.commit()

    # Get updated reactions
    reactions = Reaction.query.filter_by(message_id=message_id).all()
    reaction_list = []
    for r in reactions:
        reaction_list.append({
            'type': r.reaction_type,
            'user_id': r.user_id,
            'username': r.user.username if r.user else 'Unknown'
        })

    grouped = {}
    for r in reaction_list:
        if r['type'] not in grouped:
            grouped[r['type']] = {'type': r['type'], 'count': 0}
        grouped[r['type']]['count'] += 1

    return jsonify({
        'success': True,
        'action': action,
        'message_id': message_id,
        'reactions': list(grouped.values()),
        'user_reaction': reaction_type if action != 'removed' else None
    })


# ============ FORWARD ROUTES ============

@spa_bp.route('/forward_message', methods=['POST'])
def forward_message():
    """Forward a message to another chat"""
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


# ============ USER/SEARCH ROUTES ============

@spa_bp.route('/search', methods=['GET'])
def search():
    """Search for users, groups, and channels"""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    query = request.args.get('q', '').strip()

    if len(query) < 2:
        return jsonify({'success': True, 'results': {'users': [], 'groups': [], 'channels': []}})

    results = {'users': [], 'groups': [], 'channels': []}

    # Search users
    users = User.query.filter(
        User.id != current_user_id,
        User.username.ilike(f'%{query}%')
    ).limit(20).all()
    results['users'] = [user_to_dict(u) for u in users]

    # Search groups
    groups = Group.query.filter(
        Group.is_public == True,
        Group.name.ilike(f'%{query}%')
    ).limit(20).all()
    results['groups'] = [{
        'id': g.id,
        'name': g.name,
        'description': g.description,
        'member_count': len(g.members)
    } for g in groups]

    # Search channels
    channels = Channel.query.filter(
        Channel.is_public == True,
        Channel.name.ilike(f'%{query}%')
    ).limit(20).all()
    results['channels'] = [{
        'id': c.id,
        'name': c.name,
        'description': c.description,
        'subscriber_count': len(c.subscribers)
    } for c in channels]

    return jsonify({'success': True, 'results': results, 'query': query})


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


# ============ PROFILE ROUTES ============

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


@spa_bp.route('/profile/<int:user_id>', methods=['GET'])
def get_user_profile(user_id):
    """Get user profile by ID"""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    return jsonify({
        'success': True,
        'user': user_to_dict(user),
        'is_blocked': bool(BlockedUser.query.filter_by(user_id=current_user_id, blocked_user_id=user_id).first())
    })


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


# ============ CLEAR CHAT ROUTES ============

@spa_bp.route('/clear_chat/<int:user_id>', methods=['POST'])
def clear_chat(user_id):
    """Clear chat with a specific user"""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    Message.query.filter(
        ((Message.sender_id == current_user_id) & (Message.receiver_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.receiver_id == current_user_id))
    ).delete()

    db.session.commit()
    return jsonify({'success': True, 'message': 'Chat cleared'})


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


@spa_bp.route('/auth/status', methods=['GET'])
def auth_status():
    """Check if user is authenticated"""
    user = get_current_user()
    if user:
        return jsonify({
            'success': True,
            'authenticated': True,
            'user': user_to_dict(user)
        })
    return jsonify({
        'success': True,
        'authenticated': False,
        'user': None
    })


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


# ============ REGISTER BLUEPRINT ============

def register_spa_bp(app):
    """Register the SPA blueprint with the app"""
    app.register_blueprint(spa_bp)
from flask import Blueprint, request, jsonify, session
from datetime import datetime, timedelta
from app import db
from app.models import User, Message, GroupMember, ChannelSubscriber, BlockedUser
from app.utils.helpers import get_current_user_id, get_current_user, format_file_size

spa_chat_bp = Blueprint('spa_chat', __name__, url_prefix='/api')

# Global typing cache (shared across the module)
typing_cache = {}


@spa_chat_bp.route('/chat_list', methods=['GET'])
def chat_list_api():
    """
    Returns the unified chat list for the current user:
    personal chats, groups, channels – sorted by last message time.
    """
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    blocked_ids = get_blocked_user_ids(current_user_id)
    chats = []

    # 1. Personal chats
    sent = db.session.query(Message.receiver_id).filter_by(sender_id=current_user_id).distinct().all()
    recv = db.session.query(Message.sender_id).filter_by(receiver_id=current_user_id).distinct().all()
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

            unread = Message.query.filter_by(
                sender_id=uid, receiver_id=current_user_id, is_read=False
            ).count()

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
                'avatar_url': getattr(user, 'avatar_url', None),
                'last_message': (last.content[:50] + '...') if last and last.content and len(last.content) > 50 else (last.content if last else 'No messages yet'),
                'timestamp': timestamp,
                'unread_count': unread,
                'is_online': getattr(user, 'is_online', False),
                'is_pinned': False,
                'has_story': False,  # will be updated later
                'status_emoji': getattr(user, 'status_emoji', '')
            })

    # 2. Groups
    memberships = GroupMember.query.filter_by(user_id=current_user_id).all()
    for membership in memberships:
        group = membership.group
        if group:
            last = Message.query.filter_by(group_id=group.id).order_by(Message.timestamp.desc()).first()
            unread = Message.query.filter_by(group_id=group.id, is_read=False).filter(Message.sender_id != current_user_id).count()
            timestamp = ''
            if last and last.timestamp:
                time_diff = datetime.utcnow() - last.timestamp
                if time_diff.days == 0:
                    timestamp = last.timestamp.strftime('%H:%M')
                elif time_diff.days == 1:
                    timestamp = 'Yesterday'
                else:
                    timestamp = last.timestamp.strftime('%d.%m.%Y')
            member_count = GroupMember.query.filter_by(group_id=group.id).count()
            chats.append({
                'type': 'group',
                'id': group.id,
                'name': group.name,
                'avatar': '👥',
                'avatar_url': getattr(group, 'avatar_url', None),
                'last_message': (last.content[:50] + '...') if last and last.content and len(last.content) > 50 else (last.content if last else 'No messages yet'),
                'timestamp': timestamp,
                'unread_count': unread,
                'member_count': member_count,
                'role': membership.role,
                'is_pinned': False
            })

    # 3. Channels
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
            subscriber_count = ChannelSubscriber.query.filter_by(channel_id=channel.id).count()
            chats.append({
                'type': 'channel',
                'id': channel.id,
                'name': channel.name,
                'avatar': '📢',
                'avatar_url': getattr(channel, 'avatar_url', None),
                'last_message': (last.content[:50] + '...') if last and last.content and len(last.content) > 50 else (last.content if last else 'No posts yet'),
                'timestamp': timestamp,
                'unread_count': 0,
                'subscriber_count': subscriber_count,
                'is_owner': channel.owner_id == current_user_id,
                'is_pinned': False
            })

    # Sort chats: pinned first, then by timestamp descending
    chats.sort(key=lambda x: (not x.get('is_pinned', False), x.get('timestamp', '')), reverse=False)
    chats.sort(key=lambda x: x.get('is_pinned', False), reverse=True)

    return jsonify({'success': True, 'chats': chats})


@spa_chat_bp.route('/messages/<int:user_id>', methods=['GET'])
def get_personal_messages(user_id):
    """
    Return messages between current user and another user.
    Supports ?after=<id> for incremental refresh.
    """
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    # Check if blocked by the other user
    if BlockedUser.query.filter_by(user_id=user_id, blocked_user_id=current_user_id).first():
        return jsonify({'success': False, 'error': 'You are blocked by this user'}), 403

    after_id = request.args.get('after', 0, type=int)
    limit = request.args.get('limit', 50, type=int)

    messages = Message.query.filter(
        ((Message.sender_id == current_user_id) & (Message.receiver_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.receiver_id == current_user_id))
    ).filter(Message.id > after_id).order_by(Message.timestamp.asc()).limit(limit).all()

    result = []
    for msg in messages:
        result.append(message_to_dict(msg, current_user_id))
    return jsonify({'success': True, 'messages': result})


@spa_chat_bp.route('/send_message', methods=['POST'])
def send_personal_message():
    """
    Send a message to another user (supports reply).
    """
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    data = request.get_json()
    receiver_id = data.get('receiver_id')
    content = data.get('content', '').strip()
    reply_to_id = data.get('reply_to_id')

    if not content:
        return jsonify({'success': False, 'error': 'Message content required'}), 400

    receiver = User.query.get(receiver_id)
    if not receiver:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    if BlockedUser.query.filter_by(user_id=receiver_id, blocked_user_id=current_user_id).first():
        return jsonify({'success': False, 'error': 'You are blocked'}), 403

    new_message = Message(
        content=content,
        sender_id=current_user_id,
        receiver_id=receiver_id,
        timestamp=datetime.utcnow()
    )
    db.session.add(new_message)
    db.session.flush()

    # Handle reply
    if reply_to_id:
        original = Message.query.get(reply_to_id)
        if original:
            from app.models import Reply
            db.session.add(Reply(original_message_id=reply_to_id, reply_message_id=new_message.id))

    db.session.commit()
    return jsonify({'success': True, 'message': message_to_dict(new_message, current_user_id)})


@spa_chat_bp.route('/mark_read/<int:user_id>', methods=['POST'])
def mark_messages_read(user_id):
    """
    Mark all unread messages from a specific sender as read.
    """
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    Message.query.filter_by(
        sender_id=user_id,
        receiver_id=current_user_id,
        is_read=False
    ).update({'is_read': True, 'read_at': datetime.utcnow()})
    db.session.commit()
    return jsonify({'success': True})


# --- Typing indicators ---

@spa_chat_bp.route('/typing/<chat_type>/<int:chat_id>', methods=['POST'])
def set_typing(chat_type, chat_id):
    """
    Record that the current user is typing in a chat.
    """
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False}), 401
    key = f"{chat_type}_{chat_id}"
    if key not in typing_cache:
        typing_cache[key] = {}
    typing_cache[key][user_id] = datetime.utcnow()
    return jsonify({'success': True})


@spa_chat_bp.route('/typing/<chat_type>/<int:chat_id>', methods=['GET'])
def get_typing(chat_type, chat_id):
    """
    Return list of users currently typing in a chat (active in the last 5 seconds).
    """
    key = f"{chat_type}_{chat_id}"
    now = datetime.utcnow()
    active = []
    if key in typing_cache:
        for uid, ts in list(typing_cache[key].items()):
            if (now - ts).total_seconds() < 5:
                active.append(uid)
            else:
                del typing_cache[key][uid]
    current_id = get_current_user_id()
    users = User.query.filter(User.id.in_(active), User.id != current_id).all()
    return jsonify({'typing': [{'id': u.id, 'name': u.display_name or u.username} for u in users]})


# --- Helpers ---

def get_blocked_user_ids(user_id):
    """Return a list of ids that the user has blocked."""
    blocked = BlockedUser.query.filter_by(user_id=user_id).all()
    return [b.blocked_user_id for b in blocked]


def message_to_dict(message, current_user_id):
    """Convert a Message ORM object to a dictionary for the API response."""
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

    # Reply info
    from app.models import Reply
    reply = Reply.query.filter_by(reply_message_id=message.id).first()
    if reply:
        original = Message.query.get(reply.original_message_id)
        if original:
            msg_data['reply_to_id'] = original.id
            msg_data['reply_to_content'] = original.content[:50] if original.content else ''
            msg_data['reply_to_sender'] = original.sender.username if original.sender else ''

    # Forward info
    from app.models import Forward
    forward = Forward.query.filter_by(forwarded_message_id=message.id).first()
    if forward:
        msg_data['forwarded_from'] = forward.original_sender_name

    # Reactions (simplified count)
    from app.models import Reaction
    reactions = Reaction.query.filter_by(message_id=message.id).all()
    for r in reactions:
        if r.reaction_type not in msg_data['reactions']:
            msg_data['reactions'][r.reaction_type] = 0
        msg_data['reactions'][r.reaction_type] += 1

    return msg_data
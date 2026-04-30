from flask import Blueprint, request, jsonify
from datetime import datetime
from app import db
from app.models import User, Message, GroupMember, ChannelSubscriber, BlockedUser, Reply, Forward, Reaction
from app.utils.helpers import get_current_user_id, get_current_user, format_file_size

spa_chat_bp = Blueprint('spa_chat', __name__, url_prefix='/api')

# Global typing cache (in-memory, shared across requests)
typing_cache = {}

# --------- Helper functions ---------
def get_blocked_user_ids(user_id):
    blocked = BlockedUser.query.filter_by(user_id=user_id).all()
    return [b.blocked_user_id for b in blocked]

def get_or_create_chat(user1_id, user2_id):
    """Return the chat_id for a personal chat. If no chat exists, create one.
       In Kiselgram, chat_id is not a separate table; we use a dummy chat_id = 0 for consistency.
       The chat_id is not used for message filtering; personal messages are filtered by sender/receiver.
       Kept for backward compatibility with /api/get_chat endpoint.
    """
    # Check if any message exists between these users
    msg = Message.query.filter(
        ((Message.sender_id == user1_id) & (Message.receiver_id == user2_id)) |
        ((Message.sender_id == user2_id) & (Message.receiver_id == user1_id))
    ).first()
    if msg:
        return msg.id  # use the first message id as a pseudo chat_id (not ideal but works for old API)
    return 0  # no messages yet

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

# --------- Chat list ---------
@spa_chat_bp.route('/chat_list', methods=['GET'])
def chat_list_api():
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    blocked_ids = get_blocked_user_ids(current_user_id)
    chats = []

    # Personal chats
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
                'has_story': False,
                'status_emoji': getattr(user, 'status_emoji', '')
            })

    # Groups
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

    # Channels
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

    chats.sort(key=lambda x: (not x.get('is_pinned', False), x.get('timestamp', '')), reverse=False)
    chats.sort(key=lambda x: x.get('is_pinned', False), reverse=True)
    return jsonify({'success': True, 'chats': chats})

# --------- Messages ---------
@spa_chat_bp.route('/messages/<int:user_id>', methods=['GET'])
def get_personal_messages(user_id):
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    if BlockedUser.query.filter_by(user_id=user_id, blocked_user_id=current_user_id).first():
        return jsonify({'success': False, 'error': 'You are blocked by this user'}), 403
    after_id = request.args.get('after', 0, type=int)
    limit = request.args.get('limit', 50, type=int)
    messages = Message.query.filter(
        ((Message.sender_id == current_user_id) & (Message.receiver_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.receiver_id == current_user_id))
    ).filter(Message.id > after_id).order_by(Message.timestamp.asc()).limit(limit).all()
    return jsonify({'success': True, 'messages': [message_to_dict(msg, current_user_id) for msg in messages]})

@spa_chat_bp.route('/send_message', methods=['POST'])
def send_personal_message():
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
    new_message = Message(content=content, sender_id=current_user_id, receiver_id=receiver_id, timestamp=datetime.utcnow())
    db.session.add(new_message)
    db.session.flush()
    if reply_to_id:
        original = Message.query.get(reply_to_id)
        if original:
            db.session.add(Reply(original_message_id=reply_to_id, reply_message_id=new_message.id))
    db.session.commit()
    return jsonify({'success': True, 'message': message_to_dict(new_message, current_user_id)})

@spa_chat_bp.route('/mark_read/<int:user_id>', methods=['POST'])
def mark_messages_read(user_id):
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    Message.query.filter_by(sender_id=user_id, receiver_id=current_user_id, is_read=False).update({'is_read': True, 'read_at': datetime.utcnow()})
    db.session.commit()
    return jsonify({'success': True})

# --------- Typing indicators (HTTP polling) ---------
@spa_chat_bp.route('/typing/<chat_type>/<int:chat_id>', methods=['POST'])
def set_typing(chat_type, chat_id):
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
    users = User.query.filter(User.id.in_(active), User.id != current_id).all() if active else []
    return jsonify({'typing': [{'id': u.id, 'name': u.display_name or u.username} for u in users]})

# --------- Backward compatibility endpoints ---------
@spa_chat_bp.route('/get_chat/<int:user_id>', methods=['GET'])
def get_chat(user_id):
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    chat_id = get_or_create_chat(current_user_id, user_id)
    other_user = User.query.get(user_id)
    if not other_user:
        return jsonify({'success': False, 'error': 'User not found'}), 404
    messages = Message.query.filter(
        ((Message.sender_id == current_user_id) & (Message.receiver_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.receiver_id == current_user_id))
    ).order_by(Message.timestamp.asc()).limit(50).all()
    return jsonify({
        'success': True,
        'chat_id': chat_id,
        'other_user': {
            'id': other_user.id,
            'username': other_user.username,
            'display_name': other_user.display_name or other_user.username,
            'avatar_url': other_user.avatar_url,
            'is_online': other_user.is_online,
        },
        'messages': [message_to_dict(msg, current_user_id) for msg in messages]
    })
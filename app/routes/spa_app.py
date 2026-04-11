# app/routes/spa_app.py
# Kiselgram SPA API - Complete

from flask import Blueprint, request, jsonify, session
from datetime import datetime, timedelta
from app import db
from app.models import (
    User, Message, Group, GroupMember, Channel, ChannelSubscriber,
    Reaction, Reply, Forward, BlockedUser, Story, StoryView, StoryLike
)
from app.utils.helpers import get_current_user, get_current_user_id, format_file_size
import re
import secrets
import os
import json

spa_bp = Blueprint('spa', __name__, url_prefix='/api')


# ============ HELPER FUNCTIONS ============

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

    # Get reply info
    reply = Reply.query.filter_by(reply_message_id=message.id).first()
    if reply:
        original = Message.query.get(reply.original_message_id)
        if original:
            msg_data['reply_to_id'] = original.id
            msg_data['reply_to_content'] = original.content[:50] if original.content else ''
            msg_data['reply_to_sender'] = original.sender.username if original.sender else ''

    # Get forward info
    forward = Forward.query.filter_by(forwarded_message_id=message.id).first()
    if forward:
        msg_data['forwarded_from'] = forward.original_sender_name

    # Get reactions
    reactions = Reaction.query.filter_by(message_id=message.id).all()
    for r in reactions:
        if r.reaction_type not in msg_data['reactions']:
            msg_data['reactions'][r.reaction_type] = 0
        msg_data['reactions'][r.reaction_type] += 1

    return msg_data


# ============ CHAT LIST ============

@spa_bp.route('/chat_list', methods=['GET'])
def chat_list_api():
    try:
        current_user_id = get_current_user_id()
        if not current_user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        blocked_ids = get_blocked_user_ids(current_user_id)
        chats = []

        # Personal chats
        try:
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
                        sender_id=uid,
                        receiver_id=current_user_id,
                        is_read=False
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
                        'last_message': (last.content[:50] + '...') if last and last.content and len(
                            last.content) > 50 else (last.content if last else 'No messages yet'),
                        'timestamp': timestamp,
                        'unread_count': unread,
                        'is_online': getattr(user, 'is_online', False),
                        'is_pinned': False,
                        'has_story': has_active_story(user.id)
                    })
        except Exception as e:
            print(f"Error loading personal chats: {e}")

        # Groups
        try:
            memberships = GroupMember.query.filter_by(user_id=current_user_id).all()
            for membership in memberships:
                group = membership.group
                if group:
                    last = Message.query.filter_by(group_id=group.id).order_by(Message.timestamp.desc()).first()

                    unread = Message.query.filter_by(
                        group_id=group.id,
                        is_read=False
                    ).filter(Message.sender_id != current_user_id).count()

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
                        'last_message': (last.content[:50] + '...') if last and last.content and len(
                            last.content) > 50 else (last.content if last else 'No messages yet'),
                        'timestamp': timestamp,
                        'unread_count': unread,
                        'member_count': member_count,
                        'role': membership.role,
                        'is_pinned': False
                    })
        except Exception as e:
            print(f"Error loading groups: {e}")

        # Channels
        try:
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
                        'last_message': (last.content[:50] + '...') if last and last.content and len(
                            last.content) > 50 else (last.content if last else 'No posts yet'),
                        'timestamp': timestamp,
                        'unread_count': 0,
                        'subscriber_count': subscriber_count,
                        'is_owner': channel.owner_id == current_user_id,
                        'is_pinned': False
                    })
        except Exception as e:
            print(f"Error loading channels: {e}")

        # Sort chats - pinned first, then by timestamp
        chats.sort(key=lambda x: (not x.get('is_pinned', False), x.get('timestamp', '')), reverse=False)
        chats.sort(key=lambda x: x.get('is_pinned', False), reverse=True)

        return jsonify({'success': True, 'chats': chats})

    except Exception as e:
        print(f"Fatal error in chat_list_api: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e), 'chats': []}), 500


# ============ GLOBAL SEARCH ============

@spa_bp.route('/search/global', methods=['GET'])
def global_search():
    try:
        current_user_id = get_current_user_id()
        if not current_user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        query = request.args.get('q', '').strip()
        if len(query) < 2:
            return jsonify({'success': True, 'results': {'users': [], 'groups': [], 'channels': []}})

        results = {'users': [], 'groups': [], 'channels': []}
        blocked_ids = get_blocked_user_ids(current_user_id)

        # Users
        users = User.query.filter(
            User.id != current_user_id,
            ~User.id.in_(blocked_ids),
            (User.username.ilike(f'%{query}%')) | (User.display_name.ilike(f'%{query}%'))
        ).limit(10).all()
        results['users'] = [user_to_dict(u) for u in users]

        # Groups
        groups = Group.query.filter(
            Group.is_public == True,
            Group.name.ilike(f'%{query}%')
        ).limit(10).all()
        results['groups'] = [{'id': g.id, 'name': g.name, 'description': g.description, 'avatar_url': g.avatar_url} for
                             g in groups]

        # Channels
        channels = Channel.query.filter(
            Channel.is_public == True,
            Channel.name.ilike(f'%{query}%')
        ).limit(10).all()
        results['channels'] = [{'id': c.id, 'name': c.name, 'description': c.description, 'avatar_url': c.avatar_url}
                               for c in channels]

        return jsonify({'success': True, 'results': results})
    except Exception as e:
        print(f"Error in global_search: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ CONTACTS ============

@spa_bp.route('/contacts', methods=['GET'])
def get_contacts():
    try:
        current_user_id = get_current_user_id()
        if not current_user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        sent = db.session.query(Message.receiver_id).filter_by(sender_id=current_user_id).distinct().all()
        recv = db.session.query(Message.sender_id).filter_by(receiver_id=current_user_id).distinct().all()
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
    except Exception as e:
        print(f"Error in get_contacts: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ USERS ============

@spa_bp.route('/users', methods=['GET'])
def get_users():
    try:
        current_user_id = get_current_user_id()
        if not current_user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        search = request.args.get('search', '')
        blocked_ids = get_blocked_user_ids(current_user_id)

        query = User.query.filter(
            User.id != current_user_id,
            ~User.id.in_(blocked_ids)
        )

        if search:
            query = query.filter(
                (User.username.ilike(f'%{search}%')) |
                (User.display_name.ilike(f'%{search}%'))
            )

        users = query.limit(50).all()
        return jsonify({'success': True, 'users': [user_to_dict(u) for u in users]})
    except Exception as e:
        print(f"Error in get_users: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@spa_bp.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    try:
        current_user_id = get_current_user_id()
        if not current_user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        user = User.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404

        return jsonify({'success': True, 'user': user_to_dict(user)})
    except Exception as e:
        print(f"Error in get_user: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ MESSAGES ============

@spa_bp.route('/messages/<int:user_id>', methods=['GET'])
def get_personal_messages(user_id):
    try:
        current_user_id = get_current_user_id()
        if not current_user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        # Check if blocked
        if BlockedUser.query.filter_by(user_id=user_id, blocked_user_id=current_user_id).first():
            return jsonify({'success': False, 'error': 'You are blocked by this user'}), 403

        after_id = request.args.get('after', 0, type=int)
        limit = request.args.get('limit', 50, type=int)

        messages = Message.query.filter(
            ((Message.sender_id == current_user_id) & (Message.receiver_id == user_id)) |
            ((Message.sender_id == user_id) & (Message.receiver_id == current_user_id))
        ).filter(Message.id > after_id).order_by(Message.timestamp.asc()).limit(limit).all()

        return jsonify({'success': True, 'messages': [message_to_dict(msg, current_user_id) for msg in messages]})
    except Exception as e:
        print(f"Error in get_personal_messages: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@spa_bp.route('/group_messages/<int:group_id>', methods=['GET'])
def get_group_messages(group_id):
    try:
        current_user_id = get_current_user_id()
        if not current_user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        membership = GroupMember.query.filter_by(user_id=current_user_id, group_id=group_id).first()
        if not membership:
            return jsonify({'success': False, 'error': 'Not a member'}), 403

        after_id = request.args.get('after', 0, type=int)
        limit = request.args.get('limit', 50, type=int)

        messages = Message.query.filter_by(group_id=group_id).filter(
            Message.id > after_id
        ).order_by(Message.timestamp.asc()).limit(limit).all()

        return jsonify({'success': True, 'messages': [message_to_dict(msg, current_user_id) for msg in messages]})
    except Exception as e:
        print(f"Error in get_group_messages: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@spa_bp.route('/channel_messages/<int:channel_id>', methods=['GET'])
def get_channel_messages(channel_id):
    try:
        current_user_id = get_current_user_id()
        if not current_user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        subscription = ChannelSubscriber.query.filter_by(user_id=current_user_id, channel_id=channel_id).first()
        channel = Channel.query.get(channel_id)

        if not subscription and (not channel or channel.owner_id != current_user_id):
            return jsonify({'success': False, 'error': 'Not subscribed'}), 403

        after_id = request.args.get('after', 0, type=int)
        limit = request.args.get('limit', 50, type=int)

        messages = Message.query.filter_by(channel_id=channel_id).filter(
            Message.id > after_id
        ).order_by(Message.timestamp.asc()).limit(limit).all()

        return jsonify({'success': True, 'messages': [message_to_dict(msg, current_user_id) for msg in messages]})
    except Exception as e:
        print(f"Error in get_channel_messages: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@spa_bp.route('/send_message', methods=['POST'])
def send_personal_message():
    try:
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

        if reply_to_id:
            original = Message.query.get(reply_to_id)
            if original:
                db.session.add(Reply(original_message_id=reply_to_id, reply_message_id=new_message.id))

        db.session.commit()
        return jsonify({'success': True, 'message': message_to_dict(new_message, current_user_id)})
    except Exception as e:
        db.session.rollback()
        print(f"Error in send_personal_message: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@spa_bp.route('/send_group_message', methods=['POST'])
def send_group_message():
    try:
        current_user_id = get_current_user_id()
        if not current_user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        data = request.get_json()
        group_id = data.get('group_id')
        content = data.get('content', '').strip()
        reply_to_id = data.get('reply_to_id')

        if not content:
            return jsonify({'success': False, 'error': 'Message content required'}), 400

        membership = GroupMember.query.filter_by(user_id=current_user_id, group_id=group_id).first()
        if not membership:
            return jsonify({'success': False, 'error': 'Not a member'}), 403

        new_message = Message(
            content=content,
            sender_id=current_user_id,
            group_id=group_id,
            receiver_id=current_user_id,
            timestamp=datetime.utcnow()
        )
        db.session.add(new_message)
        db.session.flush()

        if reply_to_id:
            original = Message.query.get(reply_to_id)
            if original:
                db.session.add(Reply(original_message_id=reply_to_id, reply_message_id=new_message.id))

        db.session.commit()
        return jsonify({'success': True, 'message': message_to_dict(new_message, current_user_id)})
    except Exception as e:
        db.session.rollback()
        print(f"Error in send_group_message: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@spa_bp.route('/send_channel_message', methods=['POST'])
def send_channel_message():
    try:
        current_user_id = get_current_user_id()
        if not current_user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        data = request.get_json()
        channel_id = data.get('channel_id')
        content = data.get('content', '').strip()

        if not content:
            return jsonify({'success': False, 'error': 'Message content required'}), 400

        channel = Channel.query.get(channel_id)
        if not channel or channel.owner_id != current_user_id:
            return jsonify({'success': False, 'error': 'Only owner can post'}), 403

        new_message = Message(
            content=content,
            sender_id=current_user_id,
            channel_id=channel_id,
            receiver_id=current_user_id,
            timestamp=datetime.utcnow()
        )
        db.session.add(new_message)
        db.session.commit()

        return jsonify({'success': True, 'message': message_to_dict(new_message, current_user_id)})
    except Exception as e:
        db.session.rollback()
        print(f"Error in send_channel_message: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@spa_bp.route('/mark_read/<int:user_id>', methods=['POST'])
def mark_messages_read(user_id):
    try:
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
    except Exception as e:
        db.session.rollback()
        print(f"Error in mark_messages_read: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ REACTIONS ============

@spa_bp.route('/reactions/<int:message_id>', methods=['GET'])
def get_reactions(message_id):
    try:
        current_user_id = get_current_user_id()
        if not current_user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        reactions = Reaction.query.filter_by(message_id=message_id).all()
        grouped = {}
        for r in reactions:
            if r.reaction_type not in grouped:
                grouped[r.reaction_type] = {'type': r.reaction_type, 'count': 0}
            grouped[r.reaction_type]['count'] += 1

        # Check if current user reacted
        user_reaction = Reaction.query.filter_by(
            message_id=message_id,
            user_id=current_user_id
        ).first()

        return jsonify({
            'success': True,
            'reactions': list(grouped.values()),
            'user_reaction': user_reaction.reaction_type if user_reaction else None
        })
    except Exception as e:
        print(f"Error in get_reactions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@spa_bp.route('/reactions/add', methods=['POST'])
def add_reaction():
    try:
        current_user_id = get_current_user_id()
        if not current_user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        data = request.get_json()
        message_id = data.get('message_id')
        reaction_type = data.get('reaction_type')

        valid = ['👍', '❤️', '😂', '😮', '😢', '👏', '🔥', '🎉', '💯']
        if reaction_type not in valid:
            return jsonify({'success': False, 'error': 'Invalid reaction'}), 400

        existing = Reaction.query.filter_by(message_id=message_id, user_id=current_user_id).first()

        if existing:
            if existing.reaction_type == reaction_type:
                db.session.delete(existing)
            else:
                existing.reaction_type = reaction_type
        else:
            db.session.add(Reaction(message_id=message_id, user_id=current_user_id, reaction_type=reaction_type))

        db.session.commit()

        reactions = Reaction.query.filter_by(message_id=message_id).all()
        grouped = {}
        for r in reactions:
            if r.reaction_type not in grouped:
                grouped[r.reaction_type] = {'type': r.reaction_type, 'count': 0}
            grouped[r.reaction_type]['count'] += 1

        return jsonify({'success': True, 'reactions': list(grouped.values())})
    except Exception as e:
        db.session.rollback()
        print(f"Error in add_reaction: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ PROFILE ============

@spa_bp.route('/profile', methods=['GET'])
def get_my_profile():
    try:
        current_user_id = get_current_user_id()
        if not current_user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        user = User.query.get(current_user_id)
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404

        return jsonify({'success': True, 'user': user_to_dict(user)})
    except Exception as e:
        print(f"Error in get_my_profile: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@spa_bp.route('/profile/update', methods=['PUT'])
def update_profile():
    try:
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
            new_username = data['username'].strip().lower()
            if len(new_username) >= 3 and re.match(r'^[a-zA-Z0-9_]+$', new_username):
                existing = User.query.filter_by(username=new_username).first()
                if not existing or existing.id == current_user_id:
                    user.username = new_username
                    session['username'] = new_username

        db.session.commit()
        return jsonify({'success': True, 'user': user_to_dict(user)})
    except Exception as e:
        db.session.rollback()
        print(f"Error in update_profile: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ AUTH ============

@spa_bp.route('/auth/logout', methods=['POST'])
def spa_logout():
    try:
        user_id = session.get('user_id')
        if user_id:
            user = User.query.get(user_id)
            if user:
                user.is_online = False
                user.last_seen = datetime.utcnow()
                db.session.commit()
        session.clear()
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error in spa_logout: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ BLOCK/CLEAR ============

@spa_bp.route('/block_user/<int:user_id>', methods=['POST'])
def block_user(user_id):
    try:
        current_user_id = get_current_user_id()
        if not current_user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        if current_user_id == user_id:
            return jsonify({'success': False, 'error': 'Cannot block yourself'}), 400

        existing = BlockedUser.query.filter_by(user_id=current_user_id, blocked_user_id=user_id).first()
        if not existing:
            db.session.add(BlockedUser(user_id=current_user_id, blocked_user_id=user_id))
            db.session.commit()

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error in block_user: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@spa_bp.route('/unblock_user/<int:user_id>', methods=['POST'])
def unblock_user(user_id):
    try:
        current_user_id = get_current_user_id()
        if not current_user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        BlockedUser.query.filter_by(user_id=current_user_id, blocked_user_id=user_id).delete()
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error in unblock_user: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@spa_bp.route('/blocked_users', methods=['GET'])
def get_blocked_users():
    try:
        current_user_id = get_current_user_id()
        if not current_user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        blocks = BlockedUser.query.filter_by(user_id=current_user_id).all()
        blocked_users = []
        for block in blocks:
            user = User.query.get(block.blocked_user_id)
            if user:
                blocked_users.append(user_to_dict(user))

        return jsonify({'success': True, 'blocked_users': blocked_users})
    except Exception as e:
        print(f"Error in get_blocked_users: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@spa_bp.route('/clear_chat/<int:user_id>', methods=['POST'])
def clear_chat(user_id):
    try:
        current_user_id = get_current_user_id()
        if not current_user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        Message.query.filter(
            ((Message.sender_id == current_user_id) & (Message.receiver_id == user_id)) |
            ((Message.sender_id == user_id) & (Message.receiver_id == current_user_id))
        ).delete()
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error in clear_chat: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ LEAVE ============

@spa_bp.route('/leave_group/<int:group_id>', methods=['POST'])
def leave_group(group_id):
    try:
        current_user_id = get_current_user_id()
        if not current_user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        membership = GroupMember.query.filter_by(user_id=current_user_id, group_id=group_id).first()
        if membership and membership.role == 'owner':
            # Transfer ownership or delete group
            other_members = GroupMember.query.filter_by(group_id=group_id).filter(
                GroupMember.user_id != current_user_id).first()
            if other_members:
                other_members.role = 'owner'
            else:
                # Delete group if no other members
                Group.query.filter_by(id=group_id).delete()

        GroupMember.query.filter_by(user_id=current_user_id, group_id=group_id).delete()
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error in leave_group: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@spa_bp.route('/leave_channel/<int:channel_id>', methods=['POST'])
def leave_channel(channel_id):
    try:
        current_user_id = get_current_user_id()
        if not current_user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        ChannelSubscriber.query.filter_by(user_id=current_user_id, channel_id=channel_id).delete()
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error in leave_channel: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ STORIES ============

@spa_bp.route('/stories', methods=['GET'])
def get_stories():
    try:
        current_user_id = get_current_user_id()
        if not current_user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        # Check if premium (stories are premium feature)
        user = User.query.get(current_user_id)
        if not getattr(user, 'is_premium', False):
            return jsonify({'success': True, 'stories': [], 'premium_required': True})

        cutoff = datetime.utcnow() - timedelta(hours=24)

        sent = db.session.query(Message.receiver_id).filter_by(sender_id=current_user_id).distinct().all()
        recv = db.session.query(Message.sender_id).filter_by(receiver_id=current_user_id).distinct().all()
        contact_ids = set([id[0] for id in sent] + [id[0] for id in recv])
        contact_ids.add(current_user_id)

        stories = Story.query.filter(
            Story.user_id.in_(contact_ids),
            Story.created_at >= cutoff
        ).order_by(Story.created_at.desc()).all()

        user_stories = {}
        viewed_story_ids = {sv.story_id for sv in StoryView.query.filter_by(viewer_id=current_user_id).all()}

        for story in stories:
            user = story.user
            if user.id not in user_stories:
                user_stories[user.id] = {
                    'user_id': user.id,
                    'username': user.username,
                    'display_name': user.display_name or user.username,
                    'avatar_url': user.avatar_url,
                    'avatar_letter': user.username[0].upper() if user.username else '?',
                    'stories': [],
                    'has_unviewed': False
                }

            liked = StoryLike.query.filter_by(story_id=story.id, user_id=current_user_id).first() is not None

            story_data = {
                'id': story.id,
                'media_url': f"/uploads/{story.media_path}" if story.media_path else None,
                'media_type': story.media_type,
                'caption': story.caption,
                'created_at': story.created_at.isoformat(),
                'expires_at': (story.created_at + timedelta(hours=24)).isoformat(),
                'viewed': story.id in viewed_story_ids,
                'view_count': StoryView.query.filter_by(story_id=story.id).count(),
                'like_count': StoryLike.query.filter_by(story_id=story.id).count(),
                'liked': liked
            }

            user_stories[user.id]['stories'].append(story_data)
            if not story_data['viewed']:
                user_stories[user.id]['has_unviewed'] = True

        def get_sort_key(item):
            is_current = 0 if item['user_id'] == current_user_id else 1
            has_unviewed = 0 if item['has_unviewed'] else 1
            max_time = max([s['created_at'] for s in item['stories']]) if item['stories'] else '0'
            return (is_current, has_unviewed, max_time)

        sorted_stories = sorted(user_stories.values(), key=get_sort_key)

        return jsonify({'success': True, 'stories': sorted_stories})

    except Exception as e:
        print(f"Error in get_stories: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@spa_bp.route('/stories/create', methods=['POST'])
def create_story():
    try:
        current_user_id = get_current_user_id()
        if not current_user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        # Check premium
        user = User.query.get(current_user_id)
        if not getattr(user, 'is_premium', False):
            return jsonify({'success': False, 'error': 'Premium required for stories'}), 403

        caption = request.form.get('caption', '').strip()

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

        unique_filename = f"story_{current_user_id}_{secrets.token_urlsafe(8)}.{file_ext}"

        upload_dir = os.path.join('uploads', 'stories')
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, unique_filename)
        relative_path = os.path.join('stories', unique_filename)

        file.save(file_path)

        new_story = Story(
            user_id=current_user_id,
            media_path=relative_path,
            media_type=media_type,
            caption=caption,
            created_at=datetime.utcnow()
        )
        db.session.add(new_story)
        db.session.commit()

        return jsonify({
            'success': True,
            'story': {
                'id': new_story.id,
                'media_url': f"/uploads/{relative_path}",
                'media_type': media_type,
                'caption': caption
            }
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error in create_story: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@spa_bp.route('/stories/<int:story_id>/view', methods=['POST'])
def view_story(story_id):
    try:
        current_user_id = get_current_user_id()
        if not current_user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        existing = StoryView.query.filter_by(
            story_id=story_id,
            viewer_id=current_user_id
        ).first()

        if not existing:
            db.session.add(StoryView(story_id=story_id, viewer_id=current_user_id, viewed_at=datetime.utcnow()))
            db.session.commit()

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@spa_bp.route('/stories/<int:story_id>/like', methods=['POST'])
def like_story(story_id):
    try:
        current_user_id = get_current_user_id()
        if not current_user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        existing = StoryLike.query.filter_by(
            story_id=story_id,
            user_id=current_user_id
        ).first()

        if existing:
            db.session.delete(existing)
            liked = False
        else:
            db.session.add(StoryLike(story_id=story_id, user_id=current_user_id))
            liked = True

        db.session.commit()

        like_count = StoryLike.query.filter_by(story_id=story_id).count()

        return jsonify({'success': True, 'liked': liked, 'like_count': like_count})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@spa_bp.route('/stories/<int:story_id>', methods=['DELETE'])
def delete_story(story_id):
    try:
        current_user_id = get_current_user_id()
        if not current_user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        story = Story.query.get_or_404(story_id)

        if story.user_id != current_user_id:
            return jsonify({'success': False, 'error': 'Not authorized'}), 403

        if story.media_path:
            file_path = os.path.join('uploads', story.media_path)
            if os.path.exists(file_path):
                os.remove(file_path)

        db.session.delete(story)
        db.session.commit()

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ GROUPS ============

@spa_bp.route('/groups/create', methods=['POST'])
def create_group():
    try:
        current_user_id = get_current_user_id()
        if not current_user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        is_public = request.form.get('is_public', 'true').lower() == 'true'

        member_ids_str = request.form.get('member_ids', '[]')
        try:
            member_ids = json.loads(member_ids_str) if isinstance(member_ids_str, str) else member_ids_str
        except:
            member_ids = []

        if not name or len(name) < 3:
            return jsonify({'success': False, 'error': 'Group name must be at least 3 characters'}), 400

        invite_link = secrets.token_urlsafe(16)

        new_group = Group(
            name=name,
            description=description,
            owner_id=current_user_id,
            is_public=is_public,
            invite_link=invite_link,
            created_at=datetime.utcnow()
        )
        db.session.add(new_group)
        db.session.flush()

        if 'avatar' in request.files:
            file = request.files['avatar']
            if file and file.filename:
                ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
                filename = f"group_{new_group.id}_{secrets.token_urlsafe(8)}.{ext}"

                upload_dir = os.path.join('uploads', 'groups')
                os.makedirs(upload_dir, exist_ok=True)
                file_path = os.path.join(upload_dir, filename)

                try:
                    from PIL import Image
                    img = Image.open(file)
                    img.thumbnail((200, 200))
                    img.save(file_path)
                    new_group.avatar_url = f"/uploads/groups/{filename}"
                except:
                    file.save(file_path)
                    new_group.avatar_url = f"/uploads/groups/{filename}"

        db.session.add(GroupMember(user_id=current_user_id, group_id=new_group.id, role='owner'))

        for member_id in member_ids:
            if member_id != current_user_id:
                db.session.add(GroupMember(user_id=member_id, group_id=new_group.id, role='member'))

        db.session.commit()

        return jsonify({
            'success': True,
            'group': {'id': new_group.id, 'name': new_group.name, 'avatar_url': new_group.avatar_url}
        })
    except Exception as e:
        db.session.rollback()
        print(f"Error in create_group: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@spa_bp.route('/groups/<int:group_id>', methods=['GET'])
def get_group(group_id):
    try:
        current_user_id = get_current_user_id()
        if not current_user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        group = Group.query.get(group_id)
        if not group:
            return jsonify({'success': False, 'error': 'Group not found'}), 404

        membership = GroupMember.query.filter_by(user_id=current_user_id, group_id=group_id).first()

        members = []
        for m in GroupMember.query.filter_by(group_id=group_id).all():
            user = User.query.get(m.user_id)
            if user:
                members.append({
                    'id': user.id,
                    'username': user.username,
                    'display_name': user.display_name or user.username,
                    'avatar_url': user.avatar_url,
                    'role': m.role
                })

        return jsonify({
            'success': True,
            'group': {
                'id': group.id,
                'name': group.name,
                'description': group.description,
                'avatar_url': group.avatar_url,
                'is_public': group.is_public,
                'owner_id': group.owner_id,
                'member_count': len(members),
                'members': members,
                'is_member': membership is not None,
                'role': membership.role if membership else None
            }
        })
    except Exception as e:
        print(f"Error in get_group: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ CHANNELS ============

@spa_bp.route('/channels/create', methods=['POST'])
def create_channel():
    try:
        current_user_id = get_current_user_id()
        if not current_user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
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

        if 'avatar' in request.files:
            file = request.files['avatar']
            if file and file.filename:
                ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
                filename = f"channel_{new_channel.id}_{secrets.token_urlsafe(8)}.{ext}"

                upload_dir = os.path.join('uploads', 'channels')
                os.makedirs(upload_dir, exist_ok=True)
                file_path = os.path.join(upload_dir, filename)

                try:
                    from PIL import Image
                    img = Image.open(file)
                    img.thumbnail((200, 200))
                    img.save(file_path)
                    new_channel.avatar_url = f"/uploads/channels/{filename}"
                except:
                    file.save(file_path)
                    new_channel.avatar_url = f"/uploads/channels/{filename}"

        db.session.add(ChannelSubscriber(user_id=current_user_id, channel_id=new_channel.id))
        db.session.commit()

        return jsonify({
            'success': True,
            'channel': {'id': new_channel.id, 'name': new_channel.name, 'avatar_url': new_channel.avatar_url}
        })
    except Exception as e:
        db.session.rollback()
        print(f"Error in create_channel: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@spa_bp.route('/channels/<int:channel_id>/subscribe', methods=['POST'])
def subscribe_channel(channel_id):
    try:
        current_user_id = get_current_user_id()
        if not current_user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        existing = ChannelSubscriber.query.filter_by(user_id=current_user_id, channel_id=channel_id).first()
        if not existing:
            db.session.add(ChannelSubscriber(user_id=current_user_id, channel_id=channel_id))
            db.session.commit()

        return jsonify({'success': True, 'subscribed': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@spa_bp.route('/channels/<int:channel_id>/unsubscribe', methods=['POST'])
def unsubscribe_channel(channel_id):
    try:
        current_user_id = get_current_user_id()
        if not current_user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        ChannelSubscriber.query.filter_by(user_id=current_user_id, channel_id=channel_id).delete()
        db.session.commit()
        return jsonify({'success': True, 'subscribed': False})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ FORWARD ============

@spa_bp.route('/forward_message', methods=['POST'])
def forward_message():
    try:
        current_user_id = get_current_user_id()
        if not current_user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        data = request.get_json()
        original_id = data.get('message_id')
        target_type = data.get('target_type')
        target_id = data.get('target_id')

        original = Message.query.get(original_id)
        if not original:
            return jsonify({'success': False, 'error': 'Message not found'}), 404

        content = original.content or ""
        if original.sender:
            content = f"📨 Forwarded from {original.sender.username}:\n{content}"

        new_message = Message(
            content=content,
            sender_id=current_user_id,
            has_attachment=original.has_attachment,
            file_name=original.file_name,
            file_path=original.file_path,
            file_type=original.file_type,
            file_size=original.file_size,
            timestamp=datetime.utcnow()
        )

        if target_type == 'personal':
            new_message.receiver_id = int(target_id)
        elif target_type == 'group':
            new_message.group_id = int(target_id)
            new_message.receiver_id = current_user_id
        elif target_type == 'channel':
            new_message.channel_id = int(target_id)
            new_message.receiver_id = current_user_id

        db.session.add(new_message)
        db.session.flush()

        db.session.add(Forward(
            original_message_id=original_id,
            forwarded_message_id=new_message.id,
            forwarded_by_id=current_user_id,
            original_sender_name=original.sender.username if original.sender else 'Unknown'
        ))
        db.session.commit()

        return jsonify({'success': True, 'message': message_to_dict(new_message, current_user_id)})
    except Exception as e:
        db.session.rollback()
        print(f"Error in forward_message: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ DELETE MESSAGE ============

@spa_bp.route('/messages/<int:message_id>', methods=['DELETE'])
def delete_message(message_id):
    try:
        current_user_id = get_current_user_id()
        if not current_user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        message = Message.query.get_or_404(message_id)
        if message.sender_id != current_user_id:
            return jsonify({'success': False, 'error': 'Not authorized'}), 403

        # Delete associated file
        if message.file_path:
            file_path = os.path.join('uploads', message.file_path)
            if os.path.exists(file_path):
                os.remove(file_path)

        db.session.delete(message)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        print(f"Error in delete_message: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ PREMIUM STATUS ============

@spa_bp.route('/premium/<int:user_id>', methods=['GET'])
def check_premium(user_id):
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404

        return jsonify({
            'success': True,
            'is_premium': getattr(user, 'is_premium', False),
            'premium_since': user.premium_since.isoformat() if getattr(user, 'premium_since', None) else None,
            'premium_expires': user.premium_expires_at.isoformat() if getattr(user, 'premium_expires_at',
                                                                              None) else None
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@spa_bp.route('/upload-limit', methods=['GET'])
def get_upload_limit_api():
        try:
            from app.routes.premium import get_upload_limit
            current_user_id = get_current_user_id()
            if not current_user_id:
                return jsonify({'success': False, 'error': 'Not authenticated'}), 401

            limit = get_upload_limit(current_user_id)
            return jsonify({'success': True, 'limit': limit, 'limit_mb': limit / (1024 * 1024)})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500


def register_spa_bp(app):
    app.register_blueprint(spa_bp)
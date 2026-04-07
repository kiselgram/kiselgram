from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from app.models import User, Group, Channel, Message, GroupMember, ChannelSubscriber
from app.utils.helpers import get_current_user, get_current_user_id
import re

search_bp = Blueprint('search', __name__)

@search_bp.route('/search')
# Update the search route in search.py to match template expectations

@search_bp.route('/search')
def search():
    if not get_current_user():
        return redirect('/')

    query = request.args.get('q', '')
    search_type = request.args.get('type', 'all')
    current_user_id = get_current_user_id()

    results = {
        'users': [],
        'groups': [],
        'channels': [],
        'messages': []
    }

    if query and len(query) >= 2:
        # Search users
        if search_type in ['all', 'users']:
            users = User.query.filter(
                User.username.ilike(f'%{query}%'),
                User.id != current_user_id
            ).limit(20).all()
            results['users'] = [{
                'id': u.id,
                'username': u.username,
                'status': 'online'
            } for u in users]

        # Search groups
        if search_type in ['all', 'groups']:
            groups = Group.query.filter(
                Group.name.ilike(f'%{query}%'),
                Group.is_public == True
            ).limit(20).all()
            results['groups'] = [{
                'id': g.id,
                'name': g.name,
                'member_count': GroupMember.query.filter_by(group_id=g.id).count(),
                'is_public': g.is_public,
                'description': g.description
            } for g in groups]

        # Search channels
        if search_type in ['all', 'channels']:
            channels = Channel.query.filter(
                Channel.name.ilike(f'%{query}%'),
                Channel.is_public == True
            ).limit(20).all()
            results['channels'] = [{
                'id': c.id,
                'name': c.name,
                'subscriber_count': ChannelSubscriber.query.filter_by(channel_id=c.id).count(),
                'is_public': c.is_public,
                'description': c.description
            } for c in channels]

        # Search messages
        if search_type in ['all', 'messages']:
            messages = Message.query.filter(
                Message.content.ilike(f'%{query}%'),
                Message.group_id.is_(None),
                Message.channel_id.is_(None),
                (
                        (Message.sender_id == current_user_id) |
                        (Message.receiver_id == current_user_id)
                )
            ).order_by(Message.timestamp.desc()).limit(50).all()

            results['messages'] = [{
                'id': m.id,
                'content': m.content[:200] if m.content else '',
                'sender_username': m.sender.username,
                'timestamp': m.timestamp.strftime('%Y-%m-%d %H:%M'),
                'chat_type': 'personal',
                'chat_id': m.sender_id if m.sender_id != current_user_id else m.receiver_id,
                'chat_name': m.sender.username if m.sender_id != current_user_id else m.receiver.username if m.receiver else 'Unknown'
            } for m in messages]

    return render_template('search.html',
                           current_user=get_current_user(),
                           results=results,
                           query=query,
                           search_type=search_type)

@search_bp.route('/api/search')
def api_search():
    if not get_current_user():
        return jsonify({'error': 'Not authenticated'}), 401

    query = request.args.get('q', '')
    search_type = request.args.get('type', 'all')

    if not query or len(query) < 2:
        return jsonify({'results': {}})

    current_user_id = get_current_user_id()
    results = {}

    # Search users
    if search_type in ['all', 'users']:
        users = User.query.filter(
            User.username.ilike(f'%{query}%'),
            User.id != current_user_id
        ).limit(10).all()
        results['users'] = [{
            'id': user.id,
            'username': user.username,
            'type': 'user'
        } for user in users]

    # Search groups
    if search_type in ['all', 'groups']:
        groups = Group.query.filter(Group.name.ilike(f'%{query}%')).limit(10).all()
        filtered_groups = []
        for group in groups:
            if group.is_public or GroupMember.query.filter_by(user_id=current_user_id, group_id=group.id).first():
                filtered_groups.append({
                    'id': group.id,
                    'name': group.name,
                    'description': group.description,
                    'members_count': len(group.members),
                    'type': 'group',
                    'is_member': GroupMember.query.filter_by(user_id=current_user_id,
                                                             group_id=group.id).first() is not None
                })
        results['groups'] = filtered_groups

    # Search channels
    if search_type in ['all', 'channels']:
        channels = Channel.query.filter(Channel.name.ilike(f'%{query}%')).limit(10).all()
        filtered_channels = []
        for channel in channels:
            if channel.is_public or ChannelSubscriber.query.filter_by(user_id=current_user_id,
                                                                      channel_id=channel.id).first():
                filtered_channels.append({
                    'id': channel.id,
                    'name': channel.name,
                    'description': channel.description,
                    'subscribers_count': len(channel.subscribers),
                    'type': 'channel',
                    'is_subscribed': ChannelSubscriber.query.filter_by(user_id=current_user_id,
                                                                       channel_id=channel.id).first() is not None
                })
        results['channels'] = filtered_channels

    return jsonify({'results': results})

@search_bp.route('/api/search_messages')
def api_search_messages():
    if not get_current_user():
        return jsonify({'error': 'Not authenticated'}), 401

    query = request.args.get('q', '')
    chat_type = request.args.get('chat_type', 'all')
    chat_id = request.args.get('chat_id', type=int)

    if not query or len(query) < 2:
        return jsonify({'messages': []})

    current_user_id = get_current_user_id()
    messages = []

    if chat_type == 'all' or chat_type == 'personal':
        personal_messages = Message.query.filter(
            Message.content.ilike(f'%{query}%'),
            Message.group_id.is_(None),
            Message.channel_id.is_(None),
            (
                    (Message.sender_id == current_user_id) |
                    (Message.receiver_id == current_user_id)
            )
        ).order_by(Message.timestamp.desc()).limit(50).all()
        messages.extend(personal_messages)

    if chat_type == 'all' or chat_type == 'group':
        if chat_id:
            group_messages = Message.query.filter(
                Message.content.ilike(f'%{query}%'),
                Message.group_id == chat_id
            ).order_by(Message.timestamp.desc()).limit(50).all()
            messages.extend(group_messages)
        else:
            user_group_ids = [gm.group_id for gm in GroupMember.query.filter_by(user_id=current_user_id).all()]
            group_messages = Message.query.filter(
                Message.content.ilike(f'%{query}%'),
                Message.group_id.in_(user_group_ids)
            ).order_by(Message.timestamp.desc()).limit(50).all()
            messages.extend(group_messages)

    if chat_type == 'all' or chat_type == 'channel':
        if chat_id:
            channel_messages = Message.query.filter(
                Message.content.ilike(f'%{query}%'),
                Message.channel_id == chat_id
            ).order_by(Message.timestamp.desc()).limit(50).all()
            messages.extend(channel_messages)
        else:
            user_channel_ids = [cs.channel_id for cs in
                                ChannelSubscriber.query.filter_by(user_id=current_user_id).all()]
            channel_messages = Message.query.filter(
                Message.content.ilike(f'%{query}%'),
                Message.channel_id.in_(user_channel_ids)
            ).order_by(Message.timestamp.desc()).limit(50).all()
            messages.extend(channel_messages)

    seen_ids = set()
    unique_messages = []
    for message in messages:
        if message.id not in seen_ids:
            seen_ids.add(message.id)
            unique_messages.append(message)

    unique_messages.sort(key=lambda x: x.timestamp, reverse=True)

    messages_data = []
    for message in unique_messages[:50]:
        context = "Personal"
        chat_name = ""

        if message.group_id:
            context = "Group"
            chat_name = message.group.name
        elif message.channel_id:
            context = "Channel"
            chat_name = message.channel.name
        else:
            other_user_id = message.receiver_id if message.sender_id == current_user_id else message.sender_id
            other_user = User.query.get(other_user_id)
            chat_name = other_user.username if other_user else "Unknown"

        messages_data.append({
            'id': message.id,
            'content': message.content,
            'sender_name': message.sender.username,
            'timestamp': message.timestamp.strftime('%Y-%m-d %H:%M'),
            'context': context,
            'chat_name': chat_name,
            'chat_id': message.group_id or message.channel_id or (
                message.receiver_id if message.sender_id == current_user_id else message.sender_id),
            'chat_type': 'group' if message.group_id else 'channel' if message.channel_id else 'personal'
        })

    return jsonify({'messages': messages_data})
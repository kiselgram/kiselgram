from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime
from app import db
from app.models import User, Message, TelegramBot, GroupMember, ChannelSubscriber, Group, Channel
from app.utils.helpers import get_current_user, get_current_user_id

chats_bp = Blueprint('chats', __name__)


@chats_bp.route('/chat_list')
def chat_list():
    if not get_current_user():
        return redirect('/')

    current_user_id = get_current_user_id()
    chats_data = []

    # 1. Get personal chats
    sent_chats = db.session.query(Message.receiver_id).filter_by(sender_id=current_user_id).distinct()
    received_chats = db.session.query(Message.sender_id).filter_by(receiver_id=current_user_id).distinct()
    chat_user_ids = set([id[0] for id in sent_chats] + [id[0] for id in received_chats])

    for user_id in chat_user_ids:
        user = User.query.get(user_id)
        if user and user.id != current_user_id:
            last_message = Message.query.filter(
                ((Message.sender_id == current_user_id) & (Message.receiver_id == user_id)) |
                ((Message.sender_id == user_id) & (Message.receiver_id == current_user_id))
            ).order_by(Message.timestamp.desc()).first()

            unread_count = Message.query.filter_by(sender_id=user_id, receiver_id=current_user_id,
                                                   is_read=False).count()

            timestamp = ''
            last_message_data = None

            if last_message:
                time_diff = datetime.utcnow() - last_message.timestamp
                if time_diff.days == 0:
                    timestamp = last_message.timestamp.strftime('%H:%M')
                elif time_diff.days == 1:
                    timestamp = 'Yesterday'
                else:
                    timestamp = last_message.timestamp.strftime('%d.%m.%Y')

                last_message_data = {
                    'content': last_message.content,
                    'sender_id': last_message.sender_id,
                    'sender': {'username': last_message.sender.username}
                }

            chats_data.append({
                'type': 'personal',
                'id': user.id,
                'name': user.username,
                'last_message': last_message_data,
                'unread_count': unread_count,
                'timestamp': timestamp
            })

    # 2. Get groups the user is member of
    user_groups = GroupMember.query.filter_by(user_id=current_user_id).all()
    for membership in user_groups:
        group = membership.group
        if group:
            last_message = Message.query.filter_by(group_id=group.id).order_by(Message.timestamp.desc()).first()

            timestamp = ''
            last_message_data = None

            if last_message:
                time_diff = datetime.utcnow() - last_message.timestamp
                if time_diff.days == 0:
                    timestamp = last_message.timestamp.strftime('%H:%M')
                elif time_diff.days == 1:
                    timestamp = 'Yesterday'
                else:
                    timestamp = last_message.timestamp.strftime('%d.%m.%Y')

                last_message_data = {
                    'content': last_message.content,
                    'sender_id': last_message.sender_id,
                    'sender': {'username': last_message.sender.username}
                }

            chats_data.append({
                'type': 'group',
                'id': group.id,
                'name': group.name,
                'last_message': last_message_data,
                'unread_count': 0,
                'timestamp': timestamp
            })

    # 3. Get channels the user is subscribed to
    user_channels = ChannelSubscriber.query.filter_by(user_id=current_user_id).all()
    for subscription in user_channels:
        channel = subscription.channel
        if channel:
            last_message = Message.query.filter_by(channel_id=channel.id).order_by(Message.timestamp.desc()).first()

            timestamp = ''
            last_message_data = None

            if last_message:
                time_diff = datetime.utcnow() - last_message.timestamp
                if time_diff.days == 0:
                    timestamp = last_message.timestamp.strftime('%H:%M')
                elif time_diff.days == 1:
                    timestamp = 'Yesterday'
                else:
                    timestamp = last_message.timestamp.strftime('%d.%m.%Y')

                last_message_data = {
                    'content': last_message.content,
                    'sender_id': last_message.sender_id,
                    'sender': {'username': last_message.sender.username}
                }

            chats_data.append({
                'type': 'channel',
                'id': channel.id,
                'name': channel.name,
                'last_message': last_message_data,
                'unread_count': 0,
                'timestamp': timestamp
            })

    # Sort by most recent message
    chats_data.sort(key=lambda x: x['timestamp'] if x['timestamp'] else '', reverse=True)

    return render_template('chat_list.html',
                           current_user=get_current_user(),
                           chats=chats_data,
                           session={'user_id': current_user_id})

@chats_bp.route('/kis_info')
def kis_info():
    return render_template('kis_info.html')
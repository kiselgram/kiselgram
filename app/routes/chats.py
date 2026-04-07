from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for

from datetime import datetime
from app import db
from app.models import User, Message, TelegramBot, GroupMember, ChannelSubscriber, Group, Channel
from app.utils.helpers import get_current_user, get_current_user_id

chats_bp = Blueprint('chats', __name__)


# Update the chat_list route in chats.py to include last_message details

@chats_bp.route('/chat_list')
def chat_list():
    if not get_current_user():
        return redirect('/')

    current_user_id = get_current_user_id()

    # Get personal chats
    sent_chats = db.session.query(Message.receiver_id).filter_by(sender_id=current_user_id).distinct()
    received_chats = db.session.query(Message.sender_id).filter_by(receiver_id=current_user_id).distinct()
    chat_user_ids = set([id[0] for id in sent_chats] + [id[0] for id in received_chats])

    chats_data = []
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
                elif time_diff.days < 7:
                    timestamp = last_message.timestamp.strftime('%A')
                else:
                    timestamp = last_message.timestamp.strftime('%d.%m.%Y')

                # Create last_message dict for template
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

    # Sort by most recent
    chats_data.sort(key=lambda x: x['timestamp'] if x['timestamp'] else '', reverse=True)

    return render_template('chat_list.html',
                           current_user=get_current_user(),
                           chats=chats_data)

@chats_bp.route('/chat/<int:user_id>')
def chat(user_id):
    if not get_current_user():
        return redirect('/')

    receiver = User.query.get_or_404(user_id)
    Message.query.filter_by(sender_id=user_id, receiver_id=get_current_user_id(), is_read=False).update(
        {'is_read': True})
    db.session.commit()

    return render_template('direct_chat.html', current_user=get_current_user(), receiver=receiver)

@chats_bp.route('/users')
def users_list():
    if not get_current_user():
        return redirect('/')

    users = User.query.all()
    bots = TelegramBot.query.filter_by(is_active=True).all()
    return render_template('users_list.html', current_user=get_current_user(), users=users, bots=bots)


# Add to routes/chats.py - fix the direct chat route

@chats_bp.route('/direct/<int:user_id>')
def direct_chat(user_id):
    """Direct chat with a user (matches template expectation)"""
    if not get_current_user():
        return redirect('/')

    receiver = User.query.get_or_404(user_id)
    current_user = get_current_user()

    # Mark messages as read
    Message.query.filter_by(
        sender_id=user_id,
        receiver_id=get_current_user_id(),
        is_read=False
    ).update({'is_read': True})
    db.session.commit()

    return render_template('direct_chat.html',
                           receiver=receiver,
                           current_user=current_user,
                           session={'user_id': get_current_user_id()})
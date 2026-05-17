# app/routes/chats.py
# Kiselgram Chat Routes

from flask import Blueprint, request, jsonify, render_template, url_for, redirect
from datetime import datetime, timedelta
from app import db
from app.models import (
    User, Message, GroupMember, ChannelSubscriber,
)
from app.utils.helpers import get_current_user, get_current_user_id, format_file_size
from app.routes.spa_app import get_blocked_user_ids

chats_bp = Blueprint('chats', __name__)


@chats_bp.route('/chat_list')
def chat_list():
    """Main chat list view - serves premium or free HTML based on user status"""
    if not get_current_user():
        return redirect('/')

    current_user = get_current_user()
    current_user_id = current_user.id
    is_premium = getattr(current_user, 'is_premium', False)

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

            unread_count = Message.query.filter_by(
                sender_id=user_id,
                receiver_id=current_user_id,
                is_read=False
            ).count()

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
                    'content': last_message.content[:50] + '...' if last_message.content and len(
                        last_message.content) > 50 else last_message.content,
                    'sender_id': last_message.sender_id,
                    'sender': {'username': last_message.sender.username}
                }

            chats_data.append({
                'type': 'personal',
                'id': user.id,
                'name': user.display_name or user.username,
                'username': user.username,
                'avatar': user.username[0].upper() if user.username else '?',
                'avatar_url': getattr(user, 'avatar_url', None),
                'last_message': last_message_data,
                'unread_count': unread_count,
                'timestamp': timestamp,
                'is_online': getattr(user, 'is_online', False)
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
                    'content': last_message.content[:50] + '...' if last_message.content and len(
                        last_message.content) > 50 else last_message.content,
                    'sender_id': last_message.sender_id,
                    'sender': {'username': last_message.sender.username}
                }

            member_count = GroupMember.query.filter_by(group_id=group.id).count()

            chats_data.append({
                'type': 'group',
                'id': group.id,
                'name': group.name,
                'avatar': '👥',
                'avatar_url': getattr(group, 'avatar_url', None),
                'last_message': last_message_data,
                'unread_count': 0,
                'timestamp': timestamp,
                'member_count': member_count,
                'role': membership.role
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
                    'content': last_message.content[:50] + '...' if last_message.content and len(
                        last_message.content) > 50 else last_message.content,
                    'sender_id': last_message.sender_id,
                    'sender': {'username': last_message.sender.username}
                }

            subscriber_count = ChannelSubscriber.query.filter_by(channel_id=channel.id).count()

            chats_data.append({
                'type': 'channel',
                'id': channel.id,
                'name': channel.name,
                'avatar': '📢',
                'avatar_url': getattr(channel, 'avatar_url', None),
                'last_message': last_message_data,
                'unread_count': 0,
                'timestamp': timestamp,
                'subscriber_count': subscriber_count,
                'is_owner': channel.owner_id == current_user_id
            })

    # Sort by most recent message
    chats_data.sort(
        key=lambda x: x['timestamp'] if x['timestamp'] else '',
        reverse=True
    )

    # Serve premium or free template based on user status
    template_name = 'prem.html' if is_premium else 'free.html'

    return render_template(
        template_name,
        current_user=current_user,
        chats=chats_data,
        is_premium=is_premium,
        session={'user_id': current_user_id}
    )


@chats_bp.route('/app')
def app_redirect():
    """Redirect to chat list"""
    return redirect(url_for('chats.chat_list'))


@chats_bp.route('/app_1')
def index():
    """Root route - redirect to chat list or login"""
    if get_current_user():
        return redirect(url_for('chats.chat_list'))
    return redirect(url_for('auth.login'))

@chats_bp.route('/mobile')
def mobile():
        if not get_current_user():
            return redirect('/')

        current_user = get_current_user()
        is_premium = getattr(current_user, 'is_premium', False)
        return render_template('mobile.html', is_premium=is_premium)


@chats_bp.route('/kis_info')
def kis_info():
    """About page"""
    current_user = get_current_user()
    return render_template(
        'kis_info.html',
        current_user=current_user,
        is_premium=getattr(current_user, 'is_premium', False) if current_user else False
    )


@chats_bp.route('/premium')
def premium_page():
    """Premium landing page"""
    current_user = get_current_user()
    if not current_user:
        return redirect(url_for('auth.login'))

    return render_template(
        'premium/index.html',
        current_user=current_user,
        is_premium=getattr(current_user, 'is_premium', False)
    )


@chats_bp.route('/chat/<int:chat_id>')
def chat_detail(chat_id):
    """Direct chat view - redirects to main app with chat open"""
    if not get_current_user():
        return redirect('/')

    return redirect(url_for('chats.chat_list') + f'?chat={chat_id}')


@chats_bp.route('/group/<int:group_id>')
def group_detail(group_id):
    """Direct group view"""
    if not get_current_user():
        return redirect('/')

    return redirect(url_for('chats.chat_list') + f'?group={group_id}')


@chats_bp.route('/channel/<int:channel_id>')
def channel_detail(channel_id):
    """Direct channel view"""
    if not get_current_user():
        return redirect('/')

    return redirect(url_for('chats.chat_list') + f'?channel={channel_id}')


# app/routes/chats.py

@chats_bp.route('/@<username>')
def user_profile(username):
    """Public user profile page"""
    from app.models import User

    user = User.query.filter_by(username=username).first()

    if not user:
        return render_template('errors/404.html'), 404

    current_user = get_current_user()
    is_premium = getattr(current_user, 'is_premium', False) if current_user else False

    return render_template(
        'profile/public.html',
        profile_user=user,
        current_user=current_user,
        is_premium=is_premium
    )


# ============ CONTEXT PROCESSOR ============

@chats_bp.app_context_processor
def inject_premium_status():
    """Inject premium status into all templates"""
    current_user = get_current_user()
    return {
        'user_is_premium': getattr(current_user, 'is_premium', False) if current_user else False
    }
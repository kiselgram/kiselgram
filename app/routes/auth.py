from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from app import db
from app.models import User, Message, Channel, ChannelSubscriber, Group, GroupMember
from app.utils.helpers import hash_password, get_current_user, get_current_user_id
import re

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/', methods=['GET'])
def index():
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            return render_template('login.html', error="Username and password are required", login=True)

        password_hash = hash_password(password)
        user = User.query.filter_by(username=username).first()

        if user:
            if user.password_hash == password_hash:
                session['username'] = username
                session['user_id'] = user.id
                return redirect('/chat_list')
            else:
                return render_template('login.html', error="Invalid password", login=True)
        else:
            try:
                new_user = User(username=username, password_hash=password_hash)
                db.session.add(new_user)
                db.session.commit()
                session['username'] = username
                session['user_id'] = new_user.id
                return redirect('/chat_list')
            except:
                db.session.rollback()
                return render_template('login.html', error="Username already exists", login=True)

    return render_template('login.html', login=True)

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@auth_bp.route('/settings')
def settings():
    if not get_current_user():
        return redirect('/')

    user = User.query.get(get_current_user_id())
    return render_template('settings.html', current_user=get_current_user(), user=user)

@auth_bp.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    """Edit user profile"""
    if not get_current_user():
        return redirect('/')

    current_user_id = get_current_user_id()
    user = User.query.get(current_user_id)

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Validate username
        if username and username != user.username:
            # Check if username already exists
            existing_user = User.query.filter_by(username=username).first()
            if existing_user and existing_user.id != current_user_id:
                return render_template('edit_profile.html',
                                       error='Username already taken',
                                       user=user,
                                       current_user=get_current_user())

            if len(username) < 3:
                return render_template('edit_profile.html',
                                       error='Username must be at least 3 characters',
                                       user=user,
                                       current_user=get_current_user())

            if len(username) > 80:
                return render_template('edit_profile.html',
                                       error='Username must be less than 80 characters',
                                       user=user,
                                       current_user=get_current_user())

            # Validate username characters (alphanumeric and underscore only)
            if not re.match(r'^[a-zA-Z0-9_]+$', username):
                return render_template('edit_profile.html',
                                       error='Username can only contain letters, numbers, and underscores',
                                       user=user,
                                       current_user=get_current_user())

            user.username = username
            session['username'] = username

        # Change password if provided
        if new_password:
            # Verify current password
            if not current_password:
                return render_template('edit_profile.html',
                                       error='Current password is required to change password',
                                       user=user,
                                       current_user=get_current_user())

            if hash_password(current_password) != user.password_hash:
                return render_template('edit_profile.html',
                                       error='Current password is incorrect',
                                       user=user,
                                       current_user=get_current_user())

            if len(new_password) < 4:
                return render_template('edit_profile.html',
                                       error='New password must be at least 4 characters',
                                       user=user,
                                       current_user=get_current_user())

            if new_password != confirm_password:
                return render_template('edit_profile.html',
                                       error='New passwords do not match',
                                       user=user,
                                       current_user=get_current_user())

            user.password_hash = hash_password(new_password)

        db.session.commit()

        return redirect(url_for('auth.settings', success='Profile updated successfully'))

    return render_template('edit_profile.html',
                           user=user,
                           current_user=get_current_user())


@auth_bp.route('/privacy')
def privacy():
    """Privacy settings page"""
    if not get_current_user():
        return redirect('/')

    user = User.query.get(get_current_user_id())

    # Get blocked users (you'll need to create a BlockedUser model)
    # For now, we'll use a simple approach
    blocked_users = []

    return render_template('privacy.html',
                           user=user,
                           blocked_users=blocked_users,
                           current_user=get_current_user())


@auth_bp.route('/api/update_privacy', methods=['POST'])
def update_privacy():
    """Update privacy settings via API"""
    if not get_current_user():
        return jsonify({'error': 'Not authenticated'}), 401

    current_user_id = get_current_user_id()
    data = request.get_json()

    # Privacy settings to update
    last_seen_visibility = data.get('last_seen_visibility', 'everyone')  # everyone, contacts, nobody
    profile_photo_visibility = data.get('profile_photo_visibility', 'everyone')
    online_status_visibility = data.get('online_status_visibility', 'everyone')

    # Store in user model (you may need to add these columns to User model)
    # For now, we'll store in session or create a UserSettings model

    # TODO: Save to database
    # user = User.query.get(current_user_id)
    # user.last_seen_visibility = last_seen_visibility
    # user.profile_photo_visibility = profile_photo_visibility
    # user.online_status_visibility = online_status_visibility
    # db.session.commit()

    return jsonify({'success': True, 'message': 'Privacy settings updated'})


@auth_bp.route('/api/block_user/<int:user_id>', methods=['POST'])
def api_block_user(user_id):
    """Block a user"""
    if not get_current_user():
        return jsonify({'error': 'Not authenticated'}), 401

    current_user_id = get_current_user_id()

    # You'll need to create a BlockedUser model
    # For now, we'll implement a simple version

    # Check if already blocked
    # existing = BlockedUser.query.filter_by(
    #     user_id=current_user_id,
    #     blocked_user_id=user_id
    # ).first()
    #
    # if not existing:
    #     block = BlockedUser(user_id=current_user_id, blocked_user_id=user_id)
    #     db.session.add(block)
    #     db.session.commit()

    return jsonify({'success': True, 'message': 'User blocked'})


@auth_bp.route('/api/unblock_user/<int:user_id>', methods=['POST'])
def api_unblock_user(user_id):
    """Unblock a user"""
    if not get_current_user():
        return jsonify({'error': 'Not authenticated'}), 401

    current_user_id = get_current_user_id()

    # Delete block record
    # BlockedUser.query.filter_by(
    #     user_id=current_user_id,
    #     blocked_user_id=user_id
    # ).delete()
    # db.session.commit()

    return jsonify({'success': True, 'message': 'User unblocked'})


@auth_bp.route('/api/blocked_users')
def api_blocked_users():
    """Get list of blocked users"""
    if not get_current_user():
        return jsonify({'error': 'Not authenticated'}), 401

    current_user_id = get_current_user_id()

    # Get blocked users
    # blocked = BlockedUser.query.filter_by(user_id=current_user_id).all()
    # users = [{'id': b.blocked_user.id, 'username': b.blocked_user.username} for b in blocked]

    return jsonify({'success': True, 'blocked_users': []})


@auth_bp.route('/api/clear_all_chats', methods=['POST'])
def api_clear_all_chats():
    """Clear all chat history"""
    if not get_current_user():
        return jsonify({'error': 'Not authenticated'}), 401

    current_user_id = get_current_user_id()

    # Delete all messages where user is sender or receiver
    Message.query.filter(
        (Message.sender_id == current_user_id) |
        (Message.receiver_id == current_user_id)
    ).delete()

    db.session.commit()

    return jsonify({'success': True, 'message': 'All chats cleared'})


# Replace the api_delete_account function in routes/auth.py

@auth_bp.route('/api/delete_account', methods=['POST'])
def api_delete_account():
    """Delete user account permanently"""
    if not get_current_user():
        return jsonify({'error': 'Not authenticated'}), 401

    current_user_id = get_current_user_id()
    user = User.query.get(current_user_id)

    if not user:
        return jsonify({'error': 'User not found'}), 404

    try:
        # 1. Delete all messages where user is sender or receiver
        Message.query.filter(
            (Message.sender_id == current_user_id) |
            (Message.receiver_id == current_user_id)
        ).delete()

        # 2. Delete group memberships
        GroupMember.query.filter_by(user_id=current_user_id).delete()

        # 3. Delete channel subscriptions
        ChannelSubscriber.query.filter_by(user_id=current_user_id).delete()

        # 4. Handle groups owned by user - transfer ownership or delete
        owned_groups = Group.query.filter_by(owner_id=current_user_id).all()
        for group in owned_groups:
            # Find another admin or member to transfer ownership
            other_member = GroupMember.query.filter(
                GroupMember.group_id == group.id,
                GroupMember.user_id != current_user_id
            ).first()

            if other_member:
                # Transfer ownership to another member
                group.owner_id = other_member.user_id
                # Make the new owner an admin
                other_member.role = 'admin'
            else:
                # No other members, delete the group and its messages
                Message.query.filter_by(group_id=group.id).delete()
                GroupMember.query.filter_by(group_id=group.id).delete()
                db.session.delete(group)

        # 5. Handle channels owned by user
        owned_channels = Channel.query.filter_by(owner_id=current_user_id).all()
        for channel in owned_channels:
            # Delete channel messages and subscriptions first
            Message.query.filter_by(channel_id=channel.id).delete()
            ChannelSubscriber.query.filter_by(channel_id=channel.id).delete()
            db.session.delete(channel)

        # 6. Delete any remaining messages where user is involved
        Message.query.filter(
            (Message.sender_id == current_user_id) |
            (Message.receiver_id == current_user_id)
        ).delete()

        # 7. Finally, delete the user
        db.session.delete(user)
        db.session.commit()

        # Clear session
        session.clear()

        return jsonify({'success': True, 'message': 'Account deleted successfully'})

    except Exception as e:
        db.session.rollback()
        print(f"Error deleting account: {str(e)}")
        return jsonify({'error': str(e)}), 500


# Add to routes/auth.py

@auth_bp.route('/api/export_data', methods=['GET'])
def api_export_data():
    """Export user data as JSON"""
    if not get_current_user():
        return redirect('/login')

    current_user_id = get_current_user_id()
    user = User.query.get(current_user_id)

    # Collect user data
    data = {
        'user': {
            'id': user.id,
            'username': user.username,
            'created_at': user.created_at.isoformat() if user.created_at else None,
        },
        'messages': [],
        'groups': [],
        'channels': []
    }

    # Get all messages
    messages = Message.query.filter(
        (Message.sender_id == current_user_id) |
        (Message.receiver_id == current_user_id)
    ).order_by(Message.timestamp).all()

    for msg in messages:
        data['messages'].append({
            'id': msg.id,
            'content': msg.content,
            'sender_id': msg.sender_id,
            'receiver_id': msg.receiver_id,
            'timestamp': msg.timestamp.isoformat() if msg.timestamp else None,
            'is_read': msg.is_read,
            'has_attachment': msg.has_attachment,
            'file_name': msg.file_name,
            'file_type': msg.file_type
        })

    # Get groups
    memberships = GroupMember.query.filter_by(user_id=current_user_id).all()
    for membership in memberships:
        group = membership.group
        data['groups'].append({
            'id': group.id,
            'name': group.name,
            'description': group.description,
            'joined_at': membership.joined_at.isoformat() if membership.joined_at else None,
            'role': membership.role
        })

    # Get channels
    subscriptions = ChannelSubscriber.query.filter_by(user_id=current_user_id).all()
    for subscription in subscriptions:
        channel = subscription.channel
        data['channels'].append({
            'id': channel.id,
            'name': channel.name,
            'description': channel.description,
            'subscribed_at': subscription.subscribed_at.isoformat() if subscription.subscribed_at else None
        })

    # Return as JSON download
    from flask import Response
    import json

    response = Response(
        json.dumps(data, indent=2),
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment; filename=kiselgram_export_{user.username}.json'}
    )

    return response
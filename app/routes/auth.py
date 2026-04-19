# app/routes/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, current_app, flash
import requests
from app import db, oauth
from app.models import User, Message, Channel, ChannelSubscriber, Group, GroupMember, BlockedUser, UserSession, Report
from app.utils.helpers import hash_password, get_current_user, get_current_user_id
import re
from datetime import datetime

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')




# ========== LOGIN (username + password only) ==========
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            return render_template('login.html', error="Username and password required", username=username)

        password_hash = hash_password(password)
        user = User.query.filter_by(username=username).first()

        if user and user.password_hash == password_hash:
            session['username'] = username
            session['user_id'] = user.id
            user.is_online = True
            user.last_seen = datetime.utcnow()
            db.session.commit()
            return redirect('/chat_list')
        else:
            return render_template('login.html', error="Invalid username or password", username=username)

    return render_template('login.html')


# ========== REGISTER (username + email + password + confirm) ==========
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        # Validation
        if not username or not email or not password:
            return render_template('register.html', error='All fields are required', username=username, email=email)

        if password != confirm:
            return render_template('register.html', error='Passwords do not match', username=username, email=email)

        if len(password) < 6:
            return render_template('register.html', error='Password must be at least 6 characters', username=username, email=email)

        if len(username) < 3:
            return render_template('register.html', error='Username must be at least 3 characters', username=username, email=email)

        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            return render_template('register.html', error='Username can only contain letters, numbers, and underscores', username=username, email=email)

        # Check for existing username
        if User.query.filter_by(username=username).first():
            return render_template('register.html', error='Username already taken', username=username, email=email)

        # Check for existing email (if email column exists)
        if hasattr(User, 'email'):
            if User.query.filter_by(email=email).first():
                return render_template('register.html', error='Email already registered', username=username, email=email)

        # Create user
        password_hash = hash_password(password)
        new_user = User(username=username, password_hash=password_hash)
        if hasattr(User, 'email'):
            new_user.email = email
        # Set default values
        new_user.display_name = username
        if hasattr(new_user, 'profile_completed'):
            new_user.profile_completed = False

        db.session.add(new_user)
        db.session.commit()

        session['username'] = username
        session['user_id'] = new_user.id
        new_user.is_online = True
        new_user.last_seen = datetime.utcnow()
        db.session.commit()

        return redirect('/chat_list')

    return render_template('register.html')


# ========== GOOGLE OAUTH ==========
@auth_bp.route('/google')
def google_login():
    redirect_uri = url_for('auth.google_authorize', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route('/google/callback')
def google_authorize():
    try:
        token = oauth.google.authorize_access_token()
    except Exception as e:
        current_app.logger.error(f"OAuth token error: {e}")
        flash("Authorization with Google failed.", "error")
        return redirect(url_for('auth.login'))

    user_info = token.get('userinfo')
    if not user_info:
        resp = requests.get(
            'https://www.googleapis.com/oauth2/v3/userinfo',
            headers={'Authorization': f'Bearer {token["access_token"]}'}
        )
        user_info = resp.json()

    if not user_info:
        flash("Failed to fetch user information from Google.", "error")
        return redirect(url_for('auth.login'))

    google_id = user_info.get('sub')
    email = user_info.get('email')
    name = user_info.get('name')
    picture = user_info.get('picture')

    # Find or create user
    user = User.query.filter_by(google_id=google_id).first()
    if not user:
        # Try to find by email if email column exists
        if hasattr(User, 'email') and email:
            user = User.query.filter_by(email=email).first()

        if not user:
            # Generate a unique username from email
            base_username = email.split('@')[0] if email else 'user'
            username = base_username
            counter = 1
            while User.query.filter_by(username=username).first():
                username = f"{base_username}{counter}"
                counter += 1

            user = User(
                username=username,
                display_name=name,
                google_id=google_id,
                avatar_url=picture
            )
            if hasattr(User, 'email'):
                user.email = email
            if hasattr(user, 'profile_completed'):
                user.profile_completed = False
            db.session.add(user)
        else:
            # Link existing account to Google
            user.google_id = google_id
            if not user.avatar_url:
                user.avatar_url = picture
            if not user.display_name:
                user.display_name = name

    # Update user info on each login
    user.display_name = name
    user.avatar_url = picture
    db.session.commit()

    session['username'] = user.username
    session['user_id'] = user.id
    user.is_online = True
    user.last_seen = datetime.utcnow()
    db.session.commit()

    flash(f"Welcome, {user.display_name or user.username}!", "success")

    if hasattr(user, 'profile_completed') and not user.profile_completed:
        return redirect(url_for('auth.edit_profile'))
    return redirect('/chat_list')


# ========== LOGOUT ==========
@auth_bp.route('/logout')
def logout():
    user_id = session.get('user_id')
    if user_id:
        user = User.query.get(user_id)
        if user:
            user.is_online = False
            user.last_seen = datetime.utcnow()
            db.session.commit()
    session.clear()
    return redirect('/auth/login')

# ========== EDIT PROFILE ==========
@auth_bp.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if not get_current_user():
        return redirect('/auth/login')
    user = User.query.get(get_current_user_id())
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        display_name = request.form.get('display_name', '').strip()
        bio = request.form.get('bio', '').strip()

        if username and username != user.username:
            existing = User.query.filter_by(username=username).first()
            if existing and existing.id != user.id:
                return render_template('edit_profile.html', error='Username taken', user=user,
                                       current_user=get_current_user())
            if len(username) < 3:
                return render_template('edit_profile.html', error='Username min 3 chars', user=user,
                                       current_user=get_current_user())
            if not re.match(r'^[a-zA-Z0-9_]+$', username):
                return render_template('edit_profile.html', error='Letters, numbers, underscores only', user=user,
                                       current_user=get_current_user())
            user.username = username
            session['username'] = username

        if display_name:
            user.display_name = display_name
        if bio:
            user.bio = bio[:500]

        if hasattr(user, 'profile_completed') and user.display_name:
            user.profile_completed = True

        db.session.commit()
        return redirect(url_for('auth.settings'))

    return render_template('edit_profile.html', user=user, current_user=get_current_user())


@auth_bp.route('/profile/<username>')
def view_profile(username):
    if not get_current_user():
        return redirect('/auth/login')
    user = User.query.filter_by(username=username).first_or_404()
    return render_template('profile.html', profile_user=user, is_own_profile=(user.id == get_current_user_id()),
                           current_user=get_current_user())


# ========== API ROUTES (unchanged) ==========
@auth_bp.route('/api/login', methods=['GET', 'POST'])
def api_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400

        password_hash = hash_password(password)
        user = User.query.filter_by(username=username).first()

        if user and user.password_hash == password_hash:
            session['username'] = username
            session['user_id'] = user.id
            user.is_online = True
            user.last_seen = datetime.utcnow()
            db.session.commit()
            return jsonify({'success': True, 'redirect': '/chat_list'})
        else:
            return jsonify({'error': 'Invalid username or password'}), 401
    return jsonify({'error': 'Method not allowed'}), 405


@auth_bp.route('/api/check_username', methods=['POST'])
def api_check_username():
    if not get_current_user():
        return jsonify({'error': 'Not authenticated'}), 401
    data = request.get_json()
    username = data.get('username', '').strip()
    if len(username) < 3:
        return jsonify({'available': False, 'message': 'Min 3 characters'})
    existing = User.query.filter_by(username=username).first()
    current_user_id = get_current_user_id()
    if existing and existing.id != current_user_id:
        return jsonify({'available': False, 'message': 'Username taken'})
    return jsonify({'available': True, 'message': 'Available'})


@auth_bp.route('/api/block_user/<int:user_id>', methods=['POST'])
def api_block_user(user_id):
    if not get_current_user():
        return jsonify({'error': 'Not authenticated'}), 401
    current_user_id = get_current_user_id()
    if current_user_id == user_id:
        return jsonify({'error': 'Cannot block self'}), 400
    existing = BlockedUser.query.filter_by(user_id=current_user_id, blocked_user_id=user_id).first()
    if existing:
        return jsonify({'error': 'Already blocked'}), 400
    block = BlockedUser(user_id=current_user_id, blocked_user_id=user_id)
    db.session.add(block)
    db.session.commit()
    return jsonify({'success': True, 'message': 'User blocked'})


@auth_bp.route('/api/unblock_user/<int:user_id>', methods=['POST'])
def api_unblock_user(user_id):
    if not get_current_user():
        return jsonify({'error': 'Not authenticated'}), 401
    current_user_id = get_current_user_id()
    block = BlockedUser.query.filter_by(user_id=current_user_id, blocked_user_id=user_id).first()
    if not block:
        return jsonify({'error': 'Not blocked'}), 404
    db.session.delete(block)
    db.session.commit()
    return jsonify({'success': True, 'message': 'User unblocked'})


@auth_bp.route('/api/blocked_users')
def api_blocked_users():
    if not get_current_user():
        return jsonify({'error': 'Not authenticated'}), 401
    current_user_id = get_current_user_id()
    blocks = BlockedUser.query.filter_by(user_id=current_user_id).all()
    blocked_users = [{'id': b.blocked_user_id, 'username': b.blocked_user.username} for b in blocks if b.blocked_user]
    return jsonify({'success': True, 'blocked_users': blocked_users})


@auth_bp.route('/api/clear_all_chats', methods=['POST'])
def api_clear_all_chats():
    if not get_current_user():
        return jsonify({'error': 'Not authenticated'}), 401
    current_user_id = get_current_user_id()
    Message.query.filter((Message.sender_id == current_user_id) | (Message.receiver_id == current_user_id)).delete()
    db.session.commit()
    return jsonify({'success': True, 'message': 'All chats cleared'})


@auth_bp.route('/api/clear_chat/<int:user_id>', methods=['POST'])
def api_clear_chat(user_id):
    if not get_current_user():
        return jsonify({'error': 'Not authenticated'}), 401
    current_user_id = get_current_user_id()
    Message.query.filter(
        ((Message.sender_id == current_user_id) & (Message.receiver_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.receiver_id == current_user_id))
    ).delete()
    db.session.commit()
    return jsonify({'success': True, 'message': 'Chat cleared'})


@auth_bp.route('/api/delete_account', methods=['POST'])
def api_delete_account():
    if not get_current_user():
        return jsonify({'error': 'Not authenticated'}), 401
    current_user_id = get_current_user_id()
    user = User.query.get(current_user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    try:
        Message.query.filter((Message.sender_id == current_user_id) | (Message.receiver_id == current_user_id)).delete()
        GroupMember.query.filter_by(user_id=current_user_id).delete()
        ChannelSubscriber.query.filter_by(user_id=current_user_id).delete()
        BlockedUser.query.filter(
            (BlockedUser.user_id == current_user_id) | (BlockedUser.blocked_user_id == current_user_id)).delete()
        UserSession.query.filter_by(user_id=current_user_id).delete()
        Report.query.filter(
            (Report.reporter_id == current_user_id) | (Report.reported_user_id == current_user_id)).delete()

        owned_groups = Group.query.filter_by(owner_id=current_user_id).all()
        for group in owned_groups:
            other = GroupMember.query.filter(GroupMember.group_id == group.id,
                                             GroupMember.user_id != current_user_id).first()
            if other:
                group.owner_id = other.user_id
                other.role = 'admin'
            else:
                Message.query.filter_by(group_id=group.id).delete()
                GroupMember.query.filter_by(group_id=group.id).delete()
                db.session.delete(group)

        owned_channels = Channel.query.filter_by(owner_id=current_user_id).all()
        for channel in owned_channels:
            Message.query.filter_by(channel_id=channel.id).delete()
            ChannelSubscriber.query.filter_by(channel_id=channel.id).delete()
            db.session.delete(channel)

        db.session.delete(user)
        db.session.commit()
        session.clear()
        return jsonify({'success': True, 'message': 'Account deleted'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@auth_bp.route('/api/export_data', methods=['GET'])
def api_export_data():
    if not get_current_user():
        return redirect('/auth/login')
    current_user_id = get_current_user_id()
    user = User.query.get(current_user_id)
    data = {
        'user': user.to_dict() if hasattr(user, 'to_dict') else {'id': user.id, 'username': user.username},
        'messages': [],
        'groups': [],
        'channels': []
    }

    messages = Message.query.filter(
        (Message.sender_id == current_user_id) | (Message.receiver_id == current_user_id)).order_by(
        Message.timestamp).all()
    for msg in messages:
        data['messages'].append({
            'id': msg.id, 'content': msg.content, 'sender_id': msg.sender_id,
            'receiver_id': msg.receiver_id, 'timestamp': msg.timestamp.isoformat() if msg.timestamp else None,
            'is_read': msg.is_read, 'has_attachment': msg.has_attachment,
            'file_name': msg.file_name, 'file_type': msg.file_type
        })

    memberships = GroupMember.query.filter_by(user_id=current_user_id).all()
    for membership in memberships:
        group = membership.group
        data['groups'].append(
            {'id': group.id, 'name': group.name, 'description': group.description, 'role': membership.role})

    subscriptions = ChannelSubscriber.query.filter_by(user_id=current_user_id).all()
    for subscription in subscriptions:
        channel = subscription.channel
        data['channels'].append({'id': channel.id, 'name': channel.name, 'description': channel.description})

    from flask import Response
    import json
    return Response(json.dumps(data, indent=2), mimetype='application/json',
                    headers={'Content-Disposition': f'attachment; filename=kiselgram_export_{user.username}.json'})
# app/routes/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, current_app, flash
from flask_mail import Mail
from flask_mail import Message as MailMessage
import requests
from app import db, oauth
from app.models import User, Message, Channel, ChannelSubscriber, Group, GroupMember, BlockedUser, UserSession, Report, EmailVerification, PreloadedAvatar
from app.utils.helpers import hash_password, get_current_user, get_current_user_id
import re
from datetime import datetime, timedelta
import secrets
from flask import session, make_response

spa_auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

mail = Mail()

# ========== LOGIN (username + password) ==========
@spa_auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            return render_template('login.html', error="Username and password required", username=username)

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            if not user.email_verified:
                return render_template('login.html', error="Please verify your email first", username=username)
            session['username'] = username
            session['user_id'] = user.id
            session['display_name'] = user.display_name or user.username
            user.is_online = True
            user.last_seen = datetime.utcnow()
            db.session.commit()
            return redirect('/chat_list')
        else:
            return render_template('login.html', error="Invalid username or password", username=username)

    return render_template('login.html')


# ========== REGISTER (email + username + password + send verification email) ==========
@spa_auth_bp.route('/register', methods=['GET', 'POST'])
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

        if User.query.filter_by(username=username).first():
            return render_template('register.html', error='Username already taken', username=username, email=email)
        if User.query.filter_by(email=email).first():
            return render_template('register.html', error='Email already registered', username=username, email=email)

        # Create user with email_verified=False
        user = User(username=username, email=email, display_name=username)
        user.set_password(password)
        user.email_verified = False
        db.session.add(user)
        db.session.commit()

        # Send verification email
        try:
            token = secrets.token_urlsafe(32)
            expires = datetime.utcnow() + timedelta(hours=24)
            verification = EmailVerification(user_id=user.id, token=token, expires_at=expires)
            db.session.add(verification)
            db.session.commit()

            verify_url = url_for('auth.verify_email', token=token, _external=True)
            msg = MailMessage(subject='Verify your email – Kiselgram',
                          sender=current_app.config['MAIL_DEFAULT_SENDER'],
                          recipients=[email])
            msg.body = f'Welcome to Kiselgram!\n\nPlease verify your email by clicking the link below:\n{verify_url}\n\nThis link expires in 24 hours.'
            mail.send(msg)
        except Exception as e:
            current_app.logger.error(f"Failed to send verification email: {e}")
            # In production you might still proceed, but for now we'll just log it
            flash('Could not send verification email. Please contact support.', 'warning')

        session['pending_user_id'] = user.id
        return redirect(url_for('auth.check_email'))

    return render_template('register.html')


@spa_auth_bp.route('/check-email')
def check_email():
    return render_template('auth/check_email.html')


@spa_auth_bp.route('/verify/<token>')
def verify_email(token):
    verification = EmailVerification.query.filter_by(token=token, verified=False).first()
    if not verification or verification.expires_at < datetime.utcnow():
        flash('Invalid or expired verification link.', 'error')
        return redirect(url_for('auth.login'))

    verification.verified = True
    user = User.query.get(verification.user_id)
    user.email_verified = True
    db.session.commit()

    # Log the user in and send to complete registration
    session['user_id'] = user.id
    session['username'] = user.username
    session['display_name'] = user.display_name or user.username
    flash('Email verified! Please complete your profile.', 'success')
    return redirect(url_for('auth.complete_registration'))


@spa_auth_bp.route('/complete-registration', methods=['GET', 'POST'])
def complete_registration():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        display_name = request.form.get('display_name', '').strip()
        avatar = request.form.get('avatar', '')

        # Validate
        if len(username) < 3:
            flash('Username must be at least 3 characters.', 'error')
            return redirect(url_for('auth.complete_registration'))
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            flash('Only letters, numbers, underscores.', 'error')
            return redirect(url_for('auth.complete_registration'))
        existing = User.query.filter(User.username == username, User.id != user.id).first()
        if existing:
            flash('Username taken.', 'error')
            return redirect(url_for('auth.complete_registration'))

        user.username = username
        user.display_name = display_name or username
        if avatar:
            user.avatar_url = avatar
        db.session.commit()

        session['username'] = username
        session['display_name'] = user.display_name
        return redirect(url_for('chats.chat_list'))

    # GET: show avatar selection
    # avatars = PreloadedAvatar.query.filter(PreloadedAvatar.category != 'system').all()
    avatars = ['avatar1.jpg', 'avatar2.jpg', 'avatar3.jpg', 'avatar4.jpg']
    return render_template('chats/complete_registration.html', user=user, avatars=avatars)


# ========== GOOGLE OAUTH ==========
@spa_auth_bp.route('/google')
def google_login():
    redirect_uri = url_for('auth.google_authorize', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@spa_auth_bp.route('/google/callback')
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
        # Try to find by email
        if email:
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
                avatar_url=picture,
                email=email,
                email_verified=True  # Google accounts are pre-verified
            )
            db.session.add(user)
        else:
            # Link existing account to Google
            user.google_id = google_id
            if not user.avatar_url:
                user.avatar_url = picture
            if not user.display_name:
                user.display_name = name
            if not user.email_verified and email == user.email:
                user.email_verified = True
    else:
        # Update info on each login
        user.display_name = name
        user.avatar_url = picture
        if not user.email_verified:
            user.email_verified = True

    db.session.commit()

    session['username'] = user.username
    session['user_id'] = user.id
    session['display_name'] = user.display_name or user.username
    user.is_online = True
    user.last_seen = datetime.utcnow()
    db.session.commit()

    flash(f"Welcome, {user.display_name or user.username}!", "success")

    # If username is the auto-generated one, ask to complete registration
    if user.username.startswith('user_') or not user.display_name:
        return redirect(url_for('auth.complete_registration'))
    return redirect('/chat_list')


# ========== LOGOUT ==========
@spa_auth_bp.route('/logout')
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


# ========== API ROUTES (unchanged) ==========
@spa_auth_bp.route('/api/login', methods=['GET', 'POST'])
def api_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['username'] = username
            session['user_id'] = user.id
            user.is_online = True
            user.last_seen = datetime.utcnow()
            db.session.commit()
            return jsonify({'success': True, 'redirect': '/chat_list'})
        else:
            return jsonify({'error': 'Invalid username or password'}), 401
    return jsonify({'error': 'Method not allowed'}), 405


@spa_auth_bp.route('/api/check_username', methods=['POST'])
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

@spa_auth_bp.route('/api/get_user_id')
def get_user_id():
    user_id = session.get('user_id')
    if not user_id:
        # Return 401 – Nginx will treat this as auth failure
        return '', 401

    # Return empty body with user ID in a custom header
    response = make_response('', 204)
    response.headers['X-User-Id'] = str(user_id)
    return response
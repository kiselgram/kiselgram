from flask import Flask, render_template, request, redirect, url_for, jsonify, session, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import hashlib
import secrets
import os
import telebot
import threading
import time
import uuid
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import mimetypes
from PIL import Image
import io
import re

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'kiselgram-mobile-optimized-' + secrets.token_hex(16)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///kiselgram.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# File upload configuration
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['ALLOWED_EXTENSIONS'] = {
    'images': {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'},
    'documents': {'pdf', 'doc', 'docx', 'txt', 'rtf'},
    'archives': {'zip', 'rar', '7z'},
    'media': {'mp3', 'mp4', 'm4a', 'wav', 'ogg', 'avi', 'mov', 'mkv'}
}

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'images'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'documents'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'media'), exist_ok=True)

db = SQLAlchemy(app)

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN) if TELEGRAM_BOT_TOKEN != 'YOUR_BOT_TOKEN_HERE' else None


# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    telegram_chat_id = db.Column(db.String(50), unique=True, nullable=True)
    telegram_username = db.Column(db.String(80), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy=True)
    received_messages = db.relationship('Message', foreign_keys='Message.receiver_id', backref='receiver', lazy=True)
    owned_groups = db.relationship('Group', foreign_keys='Group.owner_id', backref='owner', lazy=True)
    group_memberships = db.relationship('GroupMember', backref='user', lazy=True)
    channel_subscriptions = db.relationship('ChannelSubscriber', backref='user', lazy=True)
    owned_channels = db.relationship('Channel', foreign_keys='Channel.owner_id', backref='owner', lazy=True)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    telegram_message_id = db.Column(db.String(50), nullable=True)
    is_from_telegram = db.Column(db.Boolean, default=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=True)

    # File attachment fields
    has_attachment = db.Column(db.Boolean, default=False)
    file_type = db.Column(db.String(20), nullable=True)
    file_name = db.Column(db.String(255), nullable=True)
    file_path = db.Column(db.String(500), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)
    thumbnail_path = db.Column(db.String(500), nullable=True)


class TelegramBot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)


class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_public = db.Column(db.Boolean, default=True)
    invite_link = db.Column(db.String(100), unique=True, nullable=True)

    members = db.relationship('GroupMember', backref='group', lazy=True)
    messages = db.relationship('Message', backref='group', lazy=True)


class GroupMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    role = db.Column(db.String(20), default='member')

    __table_args__ = (db.UniqueConstraint('user_id', 'group_id', name='unique_group_member'),)


class Channel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_public = db.Column(db.Boolean, default=True)
    invite_link = db.Column(db.String(100), unique=True, nullable=True)

    messages = db.relationship('Message', backref='channel', lazy=True)
    subscribers = db.relationship('ChannelSubscriber', backref='channel', lazy=True)


class ChannelSubscriber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=False)
    subscribed_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'channel_id', name='unique_channel_subscriber'),)


# Utility functions
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def get_current_user():
    return session.get('username')


def get_current_user_id():
    return session.get('user_id')


def generate_invite_link():
    return secrets.token_urlsafe(16)


def allowed_file(filename, file_type='all'):
    """Check if file extension is allowed"""
    if '.' not in filename:
        return False

    ext = filename.rsplit('.', 1)[1].lower()

    if file_type == 'all':
        for category in app.config['ALLOWED_EXTENSIONS'].values():
            if ext in category:
                return True
        return False
    elif file_type in app.config['ALLOWED_EXTENSIONS']:
        return ext in app.config['ALLOWED_EXTENSIONS'][file_type]

    return False


def get_file_type(filename):
    """Determine file type from extension"""
    ext = filename.rsplit('.', 1)[1].lower()

    if ext in app.config['ALLOWED_EXTENSIONS']['images']:
        return 'image'
    elif ext in app.config['ALLOWED_EXTENSIONS']['media']:
        if ext in {'mp4', 'avi', 'mov', 'mkv'}:
            return 'video'
        return 'audio'
    elif ext in app.config['ALLOWED_EXTENSIONS']['documents']:
        return 'document'
    elif ext in app.config['ALLOWED_EXTENSIONS']['archives']:
        return 'archive'
    else:
        return 'unknown'


def create_thumbnail(image_path, thumbnail_path, size=(200, 200)):
    """Create thumbnail for images"""
    try:
        with Image.open(image_path) as img:
            img.thumbnail(size)
            img.save(thumbnail_path, 'JPEG' if thumbnail_path.lower().endswith('.jpg') else 'PNG')
        return True
    except Exception as e:
        print(f"Thumbnail creation failed: {e}")
        return False


def format_file_size(size_bytes):
    """Convert bytes to human readable format"""
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1

    return f"{size_bytes:.1f} {size_names[i]}"


def setup_bots():
    """Initialize bot users"""
    bots_data = [
        {'name': 'Weather Bot', 'username': 'weather_bot', 'description': 'Get weather information'},
        {'name': 'News Bot', 'username': 'news_bot', 'description': 'Latest news headlines'},
        {'name': 'Calculator Bot', 'username': 'calc_bot', 'description': 'Mathematical calculations'},
        {'name': 'Kiselgram Help', 'username': 'kiselgram_bot', 'description': 'Official help'}
    ]

    for bot_data in bots_data:
        if not User.query.filter_by(username=bot_data['username']).first():
            bot_user = User(username=bot_data['username'], password_hash=hash_password(secrets.token_hex(16)) if bot_data['username'] != "kiselgram_bot" else "kiselgramsupport")
            db.session.add(bot_user)
        if not TelegramBot.query.filter_by(username=bot_data['username']).first():
            telegram_bot = TelegramBot(**bot_data)
            db.session.add(telegram_bot)

    db.session.commit()


# Template filter
@app.template_filter('highlight_text')
def highlight_text(text, query):
    if not text or not query:
        return text
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    return pattern.sub(lambda m: f'<span class="highlight">{m.group()}</span>', str(text))


# Routes
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            return render_template('login.html', error="Username and password are required")

        password_hash = hash_password(password)
        user = User.query.filter_by(username=username).first()

        if user:
            if user.password_hash == password_hash:
                session['username'] = username
                session['user_id'] = user.id
                return redirect('/chat_list')
            else:
                return render_template('login.html', error="Invalid password")
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
                return render_template('login.html', error="Username already exists")

    return render_template('login.html')


@app.route('/chat_list')
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
            else:
                timestamp = ''

            chats_data.append({
                'type': 'personal',
                'id': user.id,
                'name': user.username,
                'user': user,
                'last_message': last_message,
                'unread_count': unread_count,
                'timestamp': timestamp
            })

    # Get groups the user is member of
    user_groups = GroupMember.query.filter_by(user_id=current_user_id).all()
    for membership in user_groups:
        group = membership.group
        last_message = Message.query.filter_by(group_id=group.id).order_by(Message.timestamp.desc()).first()

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
        else:
            timestamp = ''

        unread_count = 0

        chats_data.append({
            'type': 'group',
            'id': group.id,
            'name': group.name,
            'group': group,
            'last_message': last_message,
            'unread_count': unread_count,
            'timestamp': timestamp
        })

    # Get channels the user is subscribed to
    user_channels = ChannelSubscriber.query.filter_by(user_id=current_user_id).all()
    for subscription in user_channels:
        channel = subscription.channel
        last_message = Message.query.filter_by(channel_id=channel.id).order_by(Message.timestamp.desc()).first()

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
        else:
            timestamp = ''

        unread_count = 0

        chats_data.append({
            'type': 'channel',
            'id': channel.id,
            'name': channel.name,
            'channel': channel,
            'last_message': last_message,
            'unread_count': unread_count,
            'timestamp': timestamp
        })

    chats_data.sort(key=lambda x: x['last_message'].timestamp if x['last_message'] else datetime.min, reverse=True)
    bots = TelegramBot.query.filter_by(is_active=True).all()

    return render_template('spa_app.html', current_user=get_current_user(), chats=chats_data, bots=bots)


# Group and Channel Management Routes
@app.route('/create_group', methods=['GET', 'POST'])
def create_group():
    if not get_current_user():
        return redirect('/')

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        is_public = request.form.get('is_public') == 'on'

        if not name:
            return render_template('create_group.html', error="Group name is required")

        try:
            invite_link = generate_invite_link()
            new_group = Group(
                name=name,
                description=description,
                owner_id=get_current_user_id(),
                is_public=is_public,
                invite_link=invite_link
            )
            db.session.add(new_group)
            db.session.flush()

            # Add creator as owner
            membership = GroupMember(
                user_id=get_current_user_id(),
                group_id=new_group.id,
                role='owner'
            )
            db.session.add(membership)
            db.session.commit()

            return redirect(f'/group/{new_group.id}')
        except Exception as e:
            db.session.rollback()
            return render_template('create_group.html', error="Error creating group")

    return render_template('create_group.html')


@app.route('/create_channel', methods=['GET', 'POST'])
def create_channel():
    if not get_current_user():
        return redirect('/')

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        is_public = request.form.get('is_public') == 'on'

        if not name:
            return render_template('create_channel.html', error="Channel name is required")

        try:
            invite_link = generate_invite_link()
            new_channel = Channel(
                name=name,
                description=description,
                owner_id=get_current_user_id(),
                is_public=is_public,
                invite_link=invite_link
            )
            db.session.add(new_channel)
            db.session.flush()

            # Add creator as subscriber
            subscription = ChannelSubscriber(
                user_id=get_current_user_id(),
                channel_id=new_channel.id
            )
            db.session.add(subscription)
            db.session.commit()

            return redirect(f'/channel/{new_channel.id}')
        except Exception as e:
            db.session.rollback()
            return render_template('create_channel.html', error="Error creating channel")

    return render_template('create_channel.html')


@app.route('/group/<int:group_id>')
def group_chat(group_id):
    if not get_current_user():
        return redirect('/')

    group = Group.query.get_or_404(group_id)
    membership = GroupMember.query.filter_by(user_id=get_current_user_id(), group_id=group_id).first()
    if not membership:
        return redirect('/join_group/' + group.invite_link)

    return render_template('group.html', current_user=get_current_user(), group=group)


@app.route('/channel/<int:channel_id>')
def channel_view(channel_id):
    if not get_current_user():
        return redirect('/')

    channel = Channel.query.get_or_404(channel_id)
    subscription = ChannelSubscriber.query.filter_by(user_id=get_current_user_id(), channel_id=channel_id).first()
    if not subscription:
        return redirect('/join_channel/' + channel.invite_link)

    return render_template('channel.html', current_user=get_current_user(), channel=channel)


@app.route('/join_group/<invite_link>')
def join_group(invite_link):
    if not get_current_user():
        return redirect('/')

    group = Group.query.filter_by(invite_link=invite_link).first_or_404()

    existing_member = GroupMember.query.filter_by(user_id=get_current_user_id(), group_id=group.id).first()
    if existing_member:
        return redirect(f'/group/{group.id}')

    try:
        membership = GroupMember(
            user_id=get_current_user_id(),
            group_id=group.id,
            role='member'
        )
        db.session.add(membership)
        db.session.commit()
        return redirect(f'/group/{group.id}')
    except:
        db.session.rollback()
        return redirect('/chat_list')


@app.route('/join_channel/<invite_link>')
def join_channel(invite_link):
    if not get_current_user():
        return redirect('/')

    channel = Channel.query.filter_by(invite_link=invite_link).first_or_404()

    existing_subscriber = ChannelSubscriber.query.filter_by(user_id=get_current_user_id(),
                                                            channel_id=channel.id).first()
    if existing_subscriber:
        return redirect(f'/channel/{channel.id}')

    try:
        subscription = ChannelSubscriber(
            user_id=get_current_user_id(),
            channel_id=channel.id
        )
        db.session.add(subscription)
        db.session.commit()
        return redirect(f'/channel/{channel.id}')
    except:
        db.session.rollback()
        return redirect('/chat_list')


@app.route('/group_info/<int:group_id>')
def group_info(group_id):
    if not get_current_user():
        return redirect('/')

    group = Group.query.get_or_404(group_id)
    membership = GroupMember.query.filter_by(user_id=get_current_user_id(), group_id=group_id).first()
    if not membership:
        return redirect('/join_group/' + group.invite_link)

    members = GroupMember.query.filter_by(group_id=group_id).all()
    return render_template('group_info.html', current_user=get_current_user(), group=group, members=members)


@app.route('/channel_info/<int:channel_id>')
def channel_info(channel_id):
    if not get_current_user():
        return redirect('/')

    channel = Channel.query.get_or_404(channel_id)
    subscription = ChannelSubscriber.query.filter_by(user_id=get_current_user_id(), channel_id=channel_id).first()
    if not subscription:
        return redirect('/join_channel/' + channel.invite_link)

    subscribers = ChannelSubscriber.query.filter_by(channel_id=channel_id).all()
    return render_template('channel_info.html', current_user=get_current_user(), channel=channel,
                           subscribers=subscribers)


@app.route('/leave_group/<int:group_id>')
def leave_group(group_id):
    if not get_current_user():
        return redirect('/')

    membership = GroupMember.query.filter_by(user_id=get_current_user_id(), group_id=group_id).first()
    if membership:
        if membership.role == 'owner':
            Message.query.filter_by(group_id=group_id).delete()
            GroupMember.query.filter_by(group_id=group_id).delete()
            Group.query.filter_by(id=group_id).delete()
        else:
            db.session.delete(membership)

        db.session.commit()

    return redirect('/chat_list')


@app.route('/leave_channel/<int:channel_id>')
def leave_channel(channel_id):
    if not get_current_user():
        return redirect('/')

    subscription = ChannelSubscriber.query.filter_by(user_id=get_current_user_id(), channel_id=channel_id).first()
    if subscription:
        db.session.delete(subscription)
        db.session.commit()

    return redirect('/chat_list')


# File upload routes
@app.route('/upload_file', methods=['POST'])
def upload_file():
    if not get_current_user():
        return jsonify({'error': 'Not authenticated'}), 401

    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # Get additional data
    receiver_id = request.form.get('receiver_id', type=int)
    group_id = request.form.get('group_id', type=int)
    channel_id = request.form.get('channel_id', type=int)
    message_text = request.form.get('message', '')

    if not receiver_id and not group_id and not channel_id:
        return jsonify({'error': 'No destination specified'}), 400

    if file and allowed_file(file.filename):
        try:
            # Generate unique filename
            file_ext = file.filename.rsplit('.', 1)[1].lower()
            unique_filename = f"{uuid.uuid4().hex}.{file_ext}"
            file_type = get_file_type(file.filename)

            # Determine upload directory
            if file_type == 'image':
                upload_dir = 'images'
            elif file_type in ['audio', 'video']:
                upload_dir = 'media'
            else:
                upload_dir = 'documents'

            file_path = os.path.join(app.config['UPLOAD_FOLDER'], upload_dir, unique_filename)
            file.save(file_path)
            file_size = os.path.getsize(file_path)

            # Create thumbnail for images
            thumbnail_path = None
            if file_type == 'image':
                thumbnail_filename = f"thumb_{unique_filename}"
                thumbnail_path = os.path.join(app.config['UPLOAD_FOLDER'], 'images', thumbnail_filename)
                if create_thumbnail(file_path, thumbnail_path):
                    thumbnail_path = f"uploads/images/{thumbnail_filename}"

            # Create message record
            new_message = Message(
                content=message_text,
                sender_id=get_current_user_id(),
                receiver_id=receiver_id or get_current_user_id(),
                group_id=group_id,
                channel_id=channel_id,
                has_attachment=True,
                file_type=file_type,
                file_name=file.filename,
                file_path=f"uploads/{upload_dir}/{unique_filename}",
                file_size=file_size,
                thumbnail_path=thumbnail_path
            )

            db.session.add(new_message)
            db.session.commit()

            return jsonify({
                'success': True,
                'message': {
                    'id': new_message.id,
                    'content': new_message.content,
                    'sender_name': new_message.sender.username,
                    'timestamp': new_message.timestamp.strftime('%H:%M'),
                    'is_own': True,
                    'has_attachment': True,
                    'file_type': new_message.file_type,
                    'file_name': new_message.file_name,
                    'file_size': format_file_size(new_message.file_size),
                    'file_url': f"/{new_message.file_path}",
                    'thumbnail_url': f"/{new_message.thumbnail_path}" if new_message.thumbnail_path else None
                }
            })

        except Exception as e:
            return jsonify({'error': f'Upload failed: {str(e)}'}), 500

    return jsonify({'error': 'File type not allowed'}), 400


@app.route('/uploads/<path:filename>')
def serve_file(filename):
    """Serve uploaded files"""
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        # Security check
        if not os.path.abspath(file_path).startswith(os.path.abspath(app.config['UPLOAD_FOLDER'])):
            return "Access denied", 403

        if os.path.exists(file_path):
            return send_file(file_path)
        else:
            return "File not found", 404
    except Exception as e:
        return str(e), 500


# API endpoints
@app.route('/api/messages/<int:user_id>')
def api_messages(user_id):
    if not get_current_user():
        return jsonify({'error': 'Not authenticated'}), 401

    current_user_id = get_current_user_id()
    after_id = request.args.get('after', 0, type=int)

    messages = Message.query.filter(
        ((Message.sender_id == current_user_id) & (Message.receiver_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.receiver_id == current_user_id))
    ).filter(Message.id > after_id).order_by(Message.timestamp.asc()).all()

    messages_data = []
    for message in messages:
        message_data = {
            'id': message.id,
            'content': message.content,
            'sender_name': message.sender.username,
            'timestamp': message.timestamp.strftime('%H:%M'),
            'is_read': message.is_read,
            'is_own': message.sender_id == current_user_id,
            'has_attachment': message.has_attachment,
        }

        if message.has_attachment:
            message_data.update({
                'file_type': message.file_type,
                'file_name': message.file_name,
                'file_size': format_file_size(message.file_size),
                'file_url': f"/{message.file_path}",
                'thumbnail_url': f"/{message.thumbnail_path}" if message.thumbnail_path else None
            })

        messages_data.append(message_data)

    return jsonify({'messages': messages_data})


@app.route('/api/group_messages/<int:group_id>')
def api_group_messages(group_id):
    if not get_current_user():
        return jsonify({'error': 'Not authenticated'}), 401

    membership = GroupMember.query.filter_by(user_id=get_current_user_id(), group_id=group_id).first()
    if not membership:
        return jsonify({'error': 'Not a member'}), 403

    after_id = request.args.get('after', 0, type=int)
    messages = Message.query.filter_by(group_id=group_id).filter(Message.id > after_id).order_by(
        Message.timestamp.asc()).all()

    messages_data = []
    for message in messages:
        message_data = {
            'id': message.id,
            'content': message.content,
            'sender_name': message.sender.username,
            'timestamp': message.timestamp.strftime('%H:%M'),
            'is_own': message.sender_id == get_current_user_id(),
            'has_attachment': message.has_attachment,
        }

        if message.has_attachment:
            message_data.update({
                'file_type': message.file_type,
                'file_name': message.file_name,
                'file_size': format_file_size(message.file_size),
                'file_url': f"/{message.file_path}",
                'thumbnail_url': f"/{message.thumbnail_path}" if message.thumbnail_path else None
            })

        messages_data.append(message_data)

    return jsonify({'messages': messages_data})


@app.route('/api/channel_messages/<int:channel_id>')
def api_channel_messages(channel_id):
    if not get_current_user():
        return jsonify({'error': 'Not authenticated'}), 401

    subscription = ChannelSubscriber.query.filter_by(user_id=get_current_user_id(), channel_id=channel_id).first()
    if not subscription:
        return jsonify({'error': 'Not subscribed'}), 403

    after_id = request.args.get('after', 0, type=int)
    messages = Message.query.filter_by(channel_id=channel_id).filter(Message.id > after_id).order_by(
        Message.timestamp.asc()).all()

    messages_data = []
    for message in messages:
        message_data = {
            'id': message.id,
            'content': message.content,
            'sender_name': message.sender.username,
            'timestamp': message.timestamp.strftime('%H:%M'),
            'is_own': message.sender_id == get_current_user_id(),
            'has_attachment': message.has_attachment,
        }

        if message.has_attachment:
            message_data.update({
                'file_type': message.file_type,
                'file_name': message.file_name,
                'file_size': format_file_size(message.file_size),
                'file_url': f"/{message.file_path}",
                'thumbnail_url': f"/{message.thumbnail_path}" if message.thumbnail_path else None
            })

        messages_data.append(message_data)

    return jsonify({'messages': messages_data})


@app.route('/api/send_message', methods=['POST'])
def api_send_message():
    if not get_current_user():
        return jsonify({'error': 'Not authenticated'}), 401

    current_user_id = get_current_user_id()
    data = request.get_json()
    receiver_id = data.get('receiver_id')
    content = data.get('content')

    if not receiver_id or (not content and not data.get('has_attachment')):
        return jsonify({'error': 'Missing parameters'}), 400

    new_message = Message(content=content, sender_id=current_user_id, receiver_id=receiver_id)
    db.session.add(new_message)
    db.session.commit()

    message_data = {
        'id': new_message.id,
        'content': new_message.content,
        'sender_name': new_message.sender.username,
        'timestamp': new_message.timestamp.strftime('%H:%M'),
        'is_own': True,
        'has_attachment': False,
    }

    return jsonify({'success': True, 'message': message_data})


@app.route('/api/send_group_message', methods=['POST'])
def api_send_group_message():
    if not get_current_user():
        return jsonify({'error': 'Not authenticated'}), 401

    current_user_id = get_current_user_id()
    data = request.get_json()
    group_id = data.get('group_id')
    content = data.get('content')

    if not group_id or (not content and not data.get('has_attachment')):
        return jsonify({'error': 'Missing parameters'}), 400

    membership = GroupMember.query.filter_by(user_id=current_user_id, group_id=group_id).first()
    if not membership:
        return jsonify({'error': 'Not a member'}), 403

    new_message = Message(content=content, sender_id=current_user_id, receiver_id=current_user_id, group_id=group_id)
    db.session.add(new_message)
    db.session.commit()

    message_data = {
        'id': new_message.id,
        'content': new_message.content,
        'sender_name': new_message.sender.username,
        'timestamp': new_message.timestamp.strftime('%H:%M'),
        'is_own': True,
        'has_attachment': False,
    }

    return jsonify({'success': True, 'message': message_data})


@app.route('/api/send_channel_message', methods=['POST'])
def api_send_channel_message():
    if not get_current_user():
        return jsonify({'error': 'Not authenticated'}), 401

    current_user_id = get_current_user_id()
    data = request.get_json()
    channel_id = data.get('channel_id')
    content = data.get('content')

    if not channel_id or (not content and not data.get('has_attachment')):
        return jsonify({'error': 'Missing parameters'}), 400

    channel = Channel.query.get(channel_id)
    if not channel or channel.owner_id != current_user_id:
        return jsonify({'error': 'Not authorized'}), 403

    new_message = Message(content=content, sender_id=current_user_id, receiver_id=current_user_id,
                          channel_id=channel_id)
    db.session.add(new_message)
    db.session.commit()

    message_data = {
        'id': new_message.id,
        'content': new_message.content,
        'sender_name': new_message.sender.username,
        'timestamp': new_message.timestamp.strftime('%H:%M'),
        'is_own': True,
        'has_attachment': False,
    }

    return jsonify({'success': True, 'message': message_data})


@app.route('/api/chat_list')
def api_chat_list():
    if not get_current_user():
        return jsonify({'error': 'Not authenticated'}), 401

    current_user_id = get_current_user_id()
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

            if last_message:
                time_diff = datetime.utcnow() - last_message.timestamp
                timestamp = last_message.timestamp.strftime(
                    '%H:%M') if time_diff.days == 0 else 'Yesterday' if time_diff.days == 1 else last_message.timestamp.strftime(
                    '%d.%m.%Y')
            else:
                timestamp = ''

            chats_data.append({
                'type': 'personal',
                'id': user.id,
                'name': user.username,
                'last_message': last_message.content if last_message else '',
                'unread_count': unread_count,
                'timestamp': timestamp,
            })

    return jsonify({'chats': chats_data})


@app.route('/users')
def users_list():
    if not get_current_user():
        return redirect('/')

    users = User.query.all()
    bots = TelegramBot.query.filter_by(is_active=True).all()
    return render_template('users_list.html', current_user=get_current_user(), users=users, bots=bots)


@app.route('/chat/<int:user_id>')
def chat(user_id):
    if not get_current_user():
        return redirect('/')

    receiver = User.query.get_or_404(user_id)
    Message.query.filter_by(sender_id=user_id, receiver_id=get_current_user_id(), is_read=False).update(
        {'is_read': True})
    db.session.commit()

    return render_template('direct_chat.html', current_user=get_current_user(), receiver=receiver)


@app.route('/settings')
def settings():
    if not get_current_user():
        return redirect('/')

    user = User.query.get(get_current_user_id())
    return render_template('settings.html', current_user=get_current_user(), user=user)


# Search Routes
@app.route('/search')
def search():
    if not get_current_user():
        return redirect('/')

    query = request.args.get('q', '')
    search_type = request.args.get('type', 'all')

    results = {
        'users': [],
        'groups': [],
        'channels': [],
        'messages': []
    }

    if query:
        current_user_id = get_current_user_id()

        # Search users
        if search_type in ['all', 'users']:
            users = User.query.filter(
                User.username.ilike(f'%{query}%'),
                User.id != current_user_id
            ).all()
            results['users'] = users

        # Search groups
        if search_type in ['all', 'groups']:
            groups = Group.query.filter(Group.name.ilike(f'%{query}%')).all()
            filtered_groups = []
            for group in groups:
                if group.is_public or GroupMember.query.filter_by(user_id=current_user_id, group_id=group.id).first():
                    filtered_groups.append(group)
            results['groups'] = filtered_groups

        # Search channels
        if search_type in ['all', 'channels']:
            channels = Channel.query.filter(Channel.name.ilike(f'%{query}%')).all()
            filtered_channels = []
            for channel in channels:
                if channel.is_public or ChannelSubscriber.query.filter_by(user_id=current_user_id,
                                                                          channel_id=channel.id).first():
                    filtered_channels.append(channel)
            results['channels'] = filtered_channels

        # Search messages
        if search_type in ['all', 'messages']:
            personal_messages = Message.query.filter(
                Message.content.ilike(f'%{query}%'),
                Message.group_id.is_(None),
                Message.channel_id.is_(None),
                (
                        (Message.sender_id == current_user_id) |
                        (Message.receiver_id == current_user_id)
                )
            ).order_by(Message.timestamp.desc()).limit(50).all()

            user_group_ids = [gm.group_id for gm in GroupMember.query.filter_by(user_id=current_user_id).all()]
            group_messages = Message.query.filter(
                Message.content.ilike(f'%{query}%'),
                Message.group_id.in_(user_group_ids)
            ).order_by(Message.timestamp.desc()).limit(50).all()

            user_channel_ids = [cs.channel_id for cs in
                                ChannelSubscriber.query.filter_by(user_id=current_user_id).all()]
            channel_messages = Message.query.filter(
                Message.content.ilike(f'%{query}%'),
                Message.channel_id.in_(user_channel_ids)
            ).order_by(Message.timestamp.desc()).limit(50).all()

            results['messages'] = personal_messages + group_messages + channel_messages

    return render_template('search.html',
                           current_user=get_current_user(),
                           results=results,
                           query=query,
                           search_type=search_type)


@app.route('/api/search')
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


@app.route('/api/search_messages')
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
            'timestamp': message.timestamp.strftime('%Y-%m-%d %H:%M'),
            'context': context,
            'chat_name': chat_name,
            'chat_id': message.group_id or message.channel_id or (
                message.receiver_id if message.sender_id == current_user_id else message.sender_id),
            'chat_type': 'group' if message.group_id else 'channel' if message.channel_id else 'personal'
        })

    return jsonify({'messages': messages_data})


# File management
@app.route('/api/delete_message/<int:message_id>', methods=['DELETE'])
def delete_message(message_id):
    if not get_current_user():
        return jsonify({'error': 'Not authenticated'}), 401

    message = Message.query.get_or_404(message_id)

    if message.sender_id != get_current_user_id():
        return jsonify({'error': 'Not authorized'}), 403

    try:
        if message.has_attachment and message.file_path:
            file_path = message.file_path
            if os.path.exists(file_path):
                os.remove(file_path)

            if message.thumbnail_path and os.path.exists(message.thumbnail_path):
                os.remove(message.thumbnail_path)

        db.session.delete(message)
        db.session.commit()

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


# Bot interaction simulation
def simulate_bot_interaction():
    """Simulate bot responses for demonstration"""
    with app.app_context():
        while True:
            try:
                bots = TelegramBot.query.filter_by(is_active=True).all()

                for bot in bots:
                    unread_messages = Message.query.filter_by(
                        receiver_id=User.query.filter_by(username=bot.username).first().id,
                        is_read=False
                    ).all()

                    for message in unread_messages:
                        message.is_read = True

                        if bot.username == 'weather_bot':
                            response = "Will be soon! Ask Ilya for the weather!"
                        elif bot.username == 'news_bot':
                            response = "📰 Breaking: Kiselgram now supports media sending! Stay tuned for more updates and also subscribe to our telegram channel: t.me/KiseIgram"
                        elif bot.username == 'calc_bot':
                            try:
                                result = eval(message.content)
                                response = f"🧮 Result: {result}"
                            except:
                                response = "❌ I can only do simple math calculations. Try something like '2+2' or '5*3'."
                        elif bot.username == 'joke_bot':
                            jokes = [
                                "Why don't scientists trust atoms? Because they make up everything!",
                                "Why did the scarecrow win an award? He was outstanding in his field!",
                                "Why don't eggs tell jokes? They'd crack each other up!"
                            ]
                            response = f"😂 {secrets.choice(jokes)}"
                        elif bot.username == 'kiselgram_bot':
                            response = "🤖 Welcome to Kiselgram Help! I can assist you with using groups, channels, and other features. What do you need help with?"
                        else:
                            response = "🤖 I'm a bot. How can I help you?"

                        bot_user = User.query.filter_by(username=bot.username).first()
                        if bot_user:
                            bot_response = Message(
                                content=response,
                                sender_id=bot_user.id,
                                receiver_id=message.sender_id,
                                is_from_telegram=True
                            )
                            db.session.add(bot_response)

                db.session.commit()
                time.sleep(5)

            except Exception as e:
                print(f"Bot simulation error: {e}")
                time.sleep(10)


def init_db():
    with app.app_context():
        db.create_all()
        setup_bots()
        print("Database initialized with complete functionality")

        # Start bot simulation
        bot_thread = threading.Thread(target=simulate_bot_interaction, daemon=True)
        bot_thread.start()


if __name__ == '__main__':
    init_db()
    print("📱 Kiselgram - Complete Messaging Platform")
    print("🌐 Running on http://localhost:5000")
    print("👥 Groups and Channels enabled")
    print("📁 File upload support enabled")
    print("🤖 Bot simulation running")
    app.run(debug=True, host='0.0.0.0', port=5001)
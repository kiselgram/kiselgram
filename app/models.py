# app/models.py

from app import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash


# ============ BASIC MODELS ============

class User(db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(80), unique=True, nullable=True)
    email_verified = db.Column(db.Boolean, default=False)
    display_name = db.Column(db.String(80), nullable=True)
    password_hash = db.Column(db.String(120), nullable=True)
    telegram_chat_id = db.Column(db.String(50), unique=True, nullable=True)
    telegram_username = db.Column(db.String(80), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    bio = db.Column(db.Text, nullable=True)
    avatar_url = db.Column(db.String(500), nullable=True)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    is_online = db.Column(db.Boolean, default=False)

    # Premium fields
    is_premium = db.Column(db.Boolean, default=False)
    premium_since = db.Column(db.DateTime, nullable=True)
    premium_expires_at = db.Column(db.DateTime, nullable=True)
    premium_auto_renew = db.Column(db.Boolean, default=False)
    premium_payment_method = db.Column(db.String(50), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    premium_plan = db.Column(db.String(20), nullable=True)

    # Avatar type
    avatar_type = "image"

    # Notification settings
    notification_sound = db.Column(db.String(50), default='default')
    per_chat_sounds = db.Column(db.JSON, default={})
    mute_all = db.Column(db.Boolean, default=False)
    do_not_disturb = db.Column(db.Boolean, default=False)

    # Bot fields
    is_bot = db.Column(db.Boolean, default=False)
    bot_owner_id = db.Column(db.Integer, nullable=True)
    bot_token = db.Column(db.String(64), nullable=True)

    # Status emoji (Premium)
    status_emoji = db.Column(db.String(10), default='')

    # Privacy settings (from Nexgram)
    privacy_last_seen = db.Column(db.String(20), default='everyone')
    privacy_photo = db.Column(db.String(20), default='everyone')
    privacy_forward = db.Column(db.String(20), default='everyone')
    privacy_calls = db.Column(db.String(20), default='everyone')
    privacy_messages = db.Column(db.String(20), default='everyone')

    # Appearance settings
    theme = db.Column(db.String(10), default='light')
    font_size = db.Column(db.Integer, default=14)
    bubble_radius = db.Column(db.Integer, default=18)
    font_family = db.Column(db.String(100), default="'Inter', sans-serif")
    my_message_color = db.Column(db.String(20), default='#667eea')
    their_message_color = db.Column(db.String(20), default='#f3f4f6')
    wallpaper = db.Column(db.String(50), default='')
    wallpaper_image = db.Column(db.String(500), nullable=True)

    # Soft delete
    is_deleted = db.Column(db.Boolean, default=False)
    deleted_at = db.Column(db.DateTime, nullable=True)

    # Google OAuth (existing)
    google_id = db.Column(db.String(100), unique=True, nullable=True)
    profile_pic = db.Column(db.String(200), nullable=True)

    # Relationships
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy=True)
    received_messages = db.relationship('Message', foreign_keys='Message.receiver_id', backref='receiver', lazy=True)
    owned_groups = db.relationship('Group', foreign_keys='Group.owner_id', backref='owner', lazy=True)
    group_memberships = db.relationship('GroupMember', backref='user', lazy=True)
    channel_subscriptions = db.relationship('ChannelSubscriber', backref='user', lazy=True)
    owned_channels = db.relationship('Channel', foreign_keys='Channel.owner_id', backref='owner', lazy=True)
    user_reactions = db.relationship('Reaction', backref='user', lazy=True)
    blocked_users = db.relationship('BlockedUser', foreign_keys='BlockedUser.user_id', backref='user', lazy=True)
    sessions = db.relationship('UserSession', backref='user', lazy=True)
    stories = db.relationship('Story', backref='user', lazy='dynamic')
    story_views = db.relationship('StoryView', backref='viewer', lazy='dynamic')
    story_likes = db.relationship('StoryLike', backref='user', lazy='dynamic')
    story_reactions = db.relationship('StoryReaction', backref='user', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'display_name': self.display_name or self.username,
            'bio': self.bio,
            'avatar_url': self.avatar_url,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'is_online': self.is_online,
            'status_emoji': self.status_emoji,
            'is_premium': self.is_premium
        }

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class TelegramBot(db.Model):
    __tablename__ = 'telegram_bot'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)


# ============ GROUP AND CHANNEL MODELS ============

class Group(db.Model):
    __tablename__ = 'groups'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_public = db.Column(db.Boolean, default=True)
    invite_link = db.Column(db.String(100), unique=True)
    avatar_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    members = db.relationship('GroupMember', backref='group', lazy='dynamic', cascade='all, delete-orphan')
    messages = db.relationship('Message', backref='group', lazy='dynamic')
    permissions = db.relationship('GroupPermission', backref='group', lazy='dynamic', cascade='all, delete-orphan')


class GroupMember(db.Model):
    __tablename__ = 'group_members'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    role = db.Column(db.String(20), default='member')

    __table_args__ = (db.UniqueConstraint('user_id', 'group_id', name='unique_group_member'),)


class GroupPermission(db.Model):
    """Role-based permissions for groups (Nexgram)"""
    __tablename__ = 'group_permissions'

    group_id = db.Column(db.Integer, db.ForeignKey('groups.id', ondelete='CASCADE'), primary_key=True)
    role = db.Column(db.String(20), primary_key=True)  # 'owner', 'admin', 'member'
    can_send_messages = db.Column(db.Boolean, default=True)
    can_send_media = db.Column(db.Boolean, default=True)
    can_add_members = db.Column(db.Boolean, default=False)
    can_pin_messages = db.Column(db.Boolean, default=False)
    can_change_info = db.Column(db.Boolean, default=False)
    can_delete_messages = db.Column(db.Boolean, default=False)
    can_ban_users = db.Column(db.Boolean, default=False)


class Channel(db.Model):
    __tablename__ = 'channels'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_public = db.Column(db.Boolean, default=True)
    invite_link = db.Column(db.String(100), unique=True)
    avatar_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    subscribers = db.relationship('ChannelSubscriber', backref='channel', lazy='dynamic', cascade='all, delete-orphan')
    messages = db.relationship('Message', backref='channel', lazy='dynamic')
    admins = db.relationship('ChannelAdmin', backref='channel', lazy='dynamic', cascade='all, delete-orphan')


class ChannelSubscriber(db.Model):
    __tablename__ = 'channel_subscribers'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    channel_id = db.Column(db.Integer, db.ForeignKey('channels.id'), nullable=False)
    subscribed_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'channel_id', name='unique_channel_subscriber'),)


class ChannelAdmin(db.Model):
    """Channel admins with specific permissions (Nexgram)"""
    __tablename__ = 'channel_admins'

    channel_id = db.Column(db.Integer, db.ForeignKey('channels.id', ondelete='CASCADE'), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    can_post = db.Column(db.Boolean, default=True)
    can_edit = db.Column(db.Boolean, default=False)
    can_delete = db.Column(db.Boolean, default=False)
    can_add_admins = db.Column(db.Boolean, default=False)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)


# ============ MESSAGE MODELS ============

class Message(db.Model):
    __tablename__ = 'message'

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    telegram_message_id = db.Column(db.String(50), nullable=True)
    is_from_telegram = db.Column(db.Boolean, default=False)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channels.id'), nullable=True)
    delivered_at = db.Column(db.DateTime, nullable=True)
    read_at = db.Column(db.DateTime, nullable=True)
    has_attachment = db.Column(db.Boolean, default=False)
    file_type = db.Column(db.String(20), nullable=True)
    file_name = db.Column(db.String(255), nullable=True)
    file_path = db.Column(db.String(500), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)
    thumbnail_path = db.Column(db.String(500), nullable=True)
    is_encrypted = db.Column(db.Boolean, default=False)
    encrypted_content = db.Column(db.Text)
    encryption_key_id = db.Column(db.Integer)

    # Soft delete
    is_deleted = db.Column(db.Boolean, default=False)
    deleted_for_all = db.Column(db.Boolean, default=False)

    # Edit timestamp
    edited_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    reactions = db.relationship('Reaction', backref='message', lazy=True, cascade='all, delete-orphan')
    replies_to = db.relationship('Reply', foreign_keys='Reply.original_message_id', backref='original_message', lazy=True)
    reply_to = db.relationship('Reply', foreign_keys='Reply.reply_message_id', backref='reply_message', uselist=False, lazy=True)
    forwards_from = db.relationship('Forward', foreign_keys='Forward.original_message_id', backref='original_message', lazy=True)
    forwards_to = db.relationship('Forward', foreign_keys='Forward.forwarded_message_id', backref='forwarded_message', uselist=False, lazy=True)


class Reaction(db.Model):
    __tablename__ = 'reaction'

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reaction_type = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('message_id', 'user_id', name='unique_user_message_reaction'),)


class Reply(db.Model):
    __tablename__ = 'reply'

    id = db.Column(db.Integer, primary_key=True)
    original_message_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=False)
    reply_message_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Forward(db.Model):
    __tablename__ = 'forward'

    id = db.Column(db.Integer, primary_key=True)
    original_message_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=False)
    forwarded_message_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=False)
    forwarded_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    original_sender_name = db.Column(db.String(80), nullable=True)


# ============ STORY MODELS ============

class Story(db.Model):
    __tablename__ = 'stories'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    media_path = db.Column(db.String(500), nullable=False)
    media_type = db.Column(db.String(20), default='image')
    caption = db.Column(db.Text)
    music_path = db.Column(db.String(500), nullable=True)          # Nexgram
    privacy_type = db.Column(db.String(20), default='everyone')   # Nexgram
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    views = db.relationship('StoryView', backref='story', lazy='dynamic', cascade='all, delete-orphan')
    likes = db.relationship('StoryLike', backref='story', lazy='dynamic', cascade='all, delete-orphan')
    reactions = db.relationship('StoryReaction', backref='story', lazy='dynamic', cascade='all, delete-orphan')


class StoryView(db.Model):
    __tablename__ = 'story_views'

    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('stories.id'), nullable=False)
    viewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow)


class StoryLike(db.Model):
    __tablename__ = 'story_likes'

    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('stories.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('story_id', 'user_id', name='unique_story_like'),)


class StoryReaction(db.Model):
    __tablename__ = 'story_reactions'

    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('stories.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reaction = db.Column(db.String(10), nullable=False)   # ❤️, 🔥, 👎, 👍
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('story_id', 'user_id', name='unique_story_reaction'),)


class StoryPrivacy(db.Model):
    """Privacy setting for a story (Nexgram)"""
    __tablename__ = 'story_privacy'

    story_id = db.Column(db.Integer, db.ForeignKey('stories.id', ondelete='CASCADE'), primary_key=True)
    privacy_type = db.Column(db.String(20), default='everyone')


class StoryAllowedUser(db.Model):
    """Users allowed to view a story with 'selected' privacy"""
    __tablename__ = 'story_allowed_users'

    story_id = db.Column(db.Integer, db.ForeignKey('stories.id', ondelete='CASCADE'), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)


# ============ CONTACT MODELS ============

class Contact(db.Model):
    __tablename__ = 'contacts'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'contact_id', name='unique_contact'),)


class ContactName(db.Model):
    """Custom name for a contact (Nexgram)"""
    __tablename__ = 'contact_names'

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    name = db.Column(db.String(80), nullable=False)


# ============ CALL MODELS ============

class Call(db.Model):
    __tablename__ = 'calls'

    id = db.Column(db.Integer, primary_key=True)
    caller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    call_type = db.Column(db.String(10), default='audio')  # 'audio' or 'video'
    status = db.Column(db.String(20), default='ringing')   # ringing, answered, ended
    duration = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class VideoCall(db.Model):
    """Persistent record of a video room session"""
    __tablename__ = 'video_calls'

    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.String(50), unique=True, nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    call_type = db.Column(db.String(10), default='video')
    status = db.Column(db.String(20), default='active')
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)
    duration = db.Column(db.Integer, default=0)
    participant_count = db.Column(db.Integer, default=1)


class VideoCallParticipant(db.Model):
    """Participants in a video call"""
    __tablename__ = 'video_call_participants'

    id = db.Column(db.Integer, primary_key=True)
    call_id = db.Column(db.Integer, db.ForeignKey('video_calls.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    left_at = db.Column(db.DateTime, nullable=True)
    audio_only = db.Column(db.Boolean, default=False)
    screensharing = db.Column(db.Boolean, default=False)


# ============ OTHER MODELS ============

class BlockedUser(db.Model):
    __tablename__ = 'blocked_users'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    blocked_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    blocked_user = db.relationship('User', foreign_keys=[blocked_user_id], backref='blocked_by')
    __table_args__ = (db.UniqueConstraint('user_id', 'blocked_user_id', name='unique_block'),)


class UserSession(db.Model):
    __tablename__ = 'user_sessions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    session_token = db.Column(db.String(255), unique=True, nullable=False)
    device = db.Column(db.String(200), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)


class Report(db.Model):
    __tablename__ = 'reports'

    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reported_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    reported_message_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=True)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    reporter = db.relationship('User', foreign_keys=[reporter_id])
    reported_user = db.relationship('User', foreign_keys=[reported_user_id])
    reported_message = db.relationship('Message', foreign_keys=[reported_message_id])


class PushSubscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    endpoint = db.Column(db.Text, nullable=False)
    p256dh = db.Column(db.Text, nullable=False)
    auth = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ============ NEXGRAM ADDITIONS ============

class Favorite(db.Model):
    __tablename__ = 'favorites'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    file_type = db.Column(db.String(20), nullable=True)
    file_path = db.Column(db.String(500), nullable=True)
    file_name = db.Column(db.String(255), nullable=True)
    note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class RecentSearch(db.Model):
    __tablename__ = 'recent_searches'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    search_query = db.Column(db.String(200), nullable=False)
    search_type = db.Column(db.String(20), default='all')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PreloadedAvatar(db.Model):
    """Pre‑loaded avatar images that users can choose during registration"""
    __tablename__ = 'preloaded_avatars'

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(100), unique=True, nullable=False)
    display_name = db.Column(db.String(50))
    category = db.Column(db.String(20), default='default')


# ============ NEW MODELS FOR MERGED FEATURES ============

class PinnedChat(db.Model):
    """Pinned chats for a user"""
    __tablename__ = 'pinned_chats'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    chat_type = db.Column(db.String(20), nullable=False)   # 'personal', 'group', 'channel'
    chat_id = db.Column(db.Integer, nullable=False)
    pinned_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'chat_type', 'chat_id', name='unique_pin'),)


class EmailVerification(db.Model):
    """Email verification tokens"""
    __tablename__ = 'email_verifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    verified = db.Column(db.Boolean, default=False)
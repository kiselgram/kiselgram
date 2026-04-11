# config.py
# Kiselgram Configuration - Loads from config/kis.toml

import os
from datetime import timedelta


def load_toml_config():
    """Load configuration from config/kis.toml"""
    try:
        import tomli
        config_path = os.path.join(os.path.dirname(__file__), 'config', 'kis.toml')
        if os.path.exists(config_path):
            with open(config_path, 'rb') as f:
                return tomli.load(f)
    except ImportError:
        print("⚠️ tomli not installed, using default config")
    except Exception as e:
        print(f"❌ Error loading config: {e}")

    return None


def get_toml_config():
    """Get configuration from kis.toml"""
    toml_config = load_toml_config()

    if not toml_config:
        return {}

    config = {}

    # App settings
    if 'app' in toml_config:
        app = toml_config['app']
        config['SECRET_KEY'] = app.get('secret_key', 'dev-secret-key')
        config['DEBUG'] = app.get('debug', False)
        config['APP_NAME'] = app.get('name', 'Kiselgram')
        config['VERSION'] = app.get('version', '2.0.0')

    # Database
    if 'database' in toml_config:
        db = toml_config['database']
        config['SQLALCHEMY_DATABASE_URI'] = db.get('url', 'sqlite:///kiselgram.db')
        config['SQLALCHEMY_ECHO'] = db.get('echo', False)

    # Upload settings
    if 'uploads' in toml_config:
        uploads = toml_config['uploads']
        config['UPLOAD_FOLDER'] = uploads.get('folder', 'uploads')
        config['MAX_CONTENT_LENGTH'] = uploads.get('max_size', 16 * 1024 * 1024)
        config['ALLOWED_IMAGES'] = uploads.get('allowed_images', ['.jpg', '.jpeg', '.png', '.gif'])
        config['ALLOWED_DOCUMENTS'] = uploads.get('allowed_documents', ['.pdf', '.doc', '.txt'])
        config['ALLOWED_VIDEOS'] = uploads.get('allowed_videos', ['.mp4', '.mov'])

    # Features
    if 'features' in toml_config:
        features = toml_config['features']
        config['FEATURE_GROUPS'] = features.get('groups', True)
        config['FEATURE_CHANNELS'] = features.get('channels', True)
        config['FEATURE_BOTS'] = features.get('bots', False)
        config['FEATURE_VIDEO_STREAMING'] = features.get('video_streaming', True)
        config['FEATURE_FILE_SHARING'] = features.get('file_sharing', True)
        config['FEATURE_REACTIONS'] = features.get('reactions', False)

    # Video streaming
    if 'video' in toml_config:
        video = toml_config['video']
        config['VIDEO_ENABLED'] = video.get('enabled', True)
        config['VIDEO_HOST'] = video.get('host', '0.0.0.0')
        config['VIDEO_PORT'] = video.get('port', 5001)
        config['VIDEO_QUALITY'] = video.get('quality', 'medium')
        config['VIDEO_MAX_SIZE'] = video.get('max_size', 100 * 1024 * 1024)

    # Telegram bot
    if 'telegram' in toml_config:
        tg = toml_config['telegram']
        config['TELEGRAM_BOT_TOKEN'] = tg.get('bot_token', '')
        config['TELEGRAM_WEBHOOK_URL'] = tg.get('webhook_url', '')

    # Server
    if 'server' in toml_config:
        server = toml_config['server']
        config['SERVER_WORKERS'] = server.get('workers', 4)
        config['SERVER_THREADED'] = server.get('threaded', True)

    # Logging
    if 'logging' in toml_config:
        config['LOGGING'] = toml_config['logging']

    return config


class Config:
    """Base configuration"""

    # Flask
    SECRET_KEY = 'dev-secret-key-change-in-production'

    # Database
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
    }

    # Upload limits
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB default

    # Upload folders
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
    STATIC_FOLDER = os.path.join(os.path.dirname(__file__), 'app', 'static')

    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_NAME = 'kiselgram_session'

    # Security
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = timedelta(days=30)

    # Premium Settings
    PREMIUM_PRICE_MONTHLY = 300  # RUB
    PREMIUM_PRICE_YEARLY = 2990  # RUB
    PREMIUM_TRIAL_DAYS = 7

    # Stickers Path
    KISEL_EMOJI_PATH = os.path.expanduser('~/Desktop/kisel_bottle_emojis/compressed')

    # Feature flags
    FEATURE_GROUPS = True
    FEATURE_CHANNELS = True
    FEATURE_BOTS = False
    FEATURE_VIDEO_STREAMING = True
    FEATURE_FILE_SHARING = True
    FEATURE_REACTIONS = False

    # Video streaming
    VIDEO_ENABLED = True
    VIDEO_HOST = '0.0.0.0'
    VIDEO_PORT = 5001
    VIDEO_QUALITY = 'medium'
    VIDEO_MAX_SIZE = 100 * 1024 * 1024

    # Telegram
    TELEGRAM_BOT_TOKEN = ''
    TELEGRAM_WEBHOOK_URL = ''

    # Cache
    CACHE_TYPE = 'SimpleCache'
    CACHE_DEFAULT_TIMEOUT = 300

    def __init__(self):
        """Load configuration from kis.toml"""
        toml_config = get_toml_config()
        for key, value in toml_config.items():
            setattr(self, key, value)


class DevelopmentConfig(Config):
    """Development configuration"""

    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(os.path.dirname(__file__), 'instance', 'kiselgram_dev.db')


class ProductionConfig(Config):
    """Production configuration"""

    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = 'https'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'postgresql://localhost/kiselgram')


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config(env=None):
    """Get configuration class based on environment"""
    if env is None:
        env = os.environ.get('FLASK_ENV', 'development')
    return config.get(env, config['default'])
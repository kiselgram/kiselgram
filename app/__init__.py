# app/__init__.py
import os
from flask import Flask, redirect, session, render_template, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail
from authlib.integrations.flask_client import OAuth
import datetime

oauth = OAuth()
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
mail = Mail()

import platform

try:
    # freedesktop_os_release returns a dict of OS details
    info = platform.freedesktop_os_release()
    production = info.get("NAME") == "Ubuntu"
except (AttributeError, OSError):
    # Fallback for Windows/macOS or older Python versions where the method doesn't exist
    production = False



def create_app():
    from app.utils.helpers import get_current_user
    from app.models import User

    basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

    app = Flask(__name__,
                template_folder=os.path.join(basedir, 'templates'),
                static_folder=os.path.join(basedir, 'static'),
                instance_path=os.path.join(basedir, 'instance')
                )

    # Load TOML config
    try:
        import tomli
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'kis.toml')
        with open(config_path, 'rb') as f:
            config = tomli.load(f)

        # App settings
        app.config['SECRET_KEY'] = config['app'].get('secret_key', 'dev-key')
        app.config['DEBUG'] = config['app'].get('debug', False)

        # Database – fix the path
        db_url = config['database']['url']
        if db_url.startswith('sqlite:///'):
            db_path = db_url.replace('sqlite:///', '')
            if not os.path.isabs(db_path):
                db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), db_path)
            db_url = f'sqlite:///{db_path}'

        app.config['SQLALCHEMY_DATABASE_URI'] = db_url if not production else "postgresql://kiselgram_user:String-123@localhost:5432/kiselgram"
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

        print(f"✅ Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")

        # Email settings from config.toml if present, otherwise fallback
        if 'mail' in config:
            app.config['MAIL_SERVER'] = config['mail'].get('server', 'mail.kiselgram.ru')
            app.config['MAIL_PORT'] = config['mail'].get('port', 587)
            app.config['MAIL_USE_TLS'] = True
            app.config['MAIL_USERNAME'] = config['mail'].get('username', 'auth@mail.kiselgram.ru')
            app.config['MAIL_PASSWORD'] = config['mail'].get('password', 'KiselgramBackend2026')
            app.config['MAIL_DEFAULT_SENDER'] = (config['mail'].get('sender_name', 'Kiselgram'),
                                                  config['mail'].get('sender_email', 'auth@mail.kiselgram.ru'))
        else:
            # Use hardcoded values as provided
            app.config['MAIL_SERVER'] = 'mail.kiselgram.ru'
            app.config['MAIL_PORT'] = 587
            app.config['MAIL_USE_TLS'] = True
            app.config['MAIL_USERNAME'] = 'auth@mail.kiselgram.ru'
            app.config['MAIL_PASSWORD'] = 'KiselgramBackend2026'
            app.config['MAIL_DEFAULT_SENDER'] = ('Kiselgram', 'auth@mail.kiselgram.ru')

    except Exception as e:
        print(f"⚠️ Error loading config: {e}")
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'kiselgram.db')

    app.config['GOOGLE_CLIENT_ID'] = config['google']['client_id']
    app.config['GOOGLE_CLIENT_SECRET'] = config['google']['client_secret']

    # Initialize extensions
    oauth.init_app(app)
    mail.init_app(app)

    # Register OAuth provider
    oauth.register(
        name='google',
        client_id=app.config['GOOGLE_CLIENT_ID'],
        client_secret=app.config['GOOGLE_CLIENT_SECRET'],
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'}
    )

    # Ensure instance folder exists
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'

    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return User.query.get(int(user_id))

    # Register blueprints
    from app.routes import spa, premium, files
    spa.register_spa_blueprints(app)
    app.register_blueprint(premium.premium_bp)
    app.register_blueprint(files.files_bp)

    # Register video blueprint if enabled
    if app.config.get('VIDEO_ENABLED', False):
        try:
            from app.routes import video
            app.register_blueprint(video.video_bp)
        except ImportError:
            pass

    # ================================================================
    # Nginx reverse proxy internal endpoint – returns the current user ID
    # ================================================================
    @app.route('/api/get_user_id')
    def get_user_id():
        user_id = session.get('user_id')
        if user_id is None:
            return '', 401
        resp = make_response('', 204)
        resp.headers['X-User-Id'] = str(user_id)
        return resp

    @app.route('/', methods=['GET'])
    def index():
        return render_template("kiselgram-home.html")

    @app.route('/logout', methods=['GET'])
    def logout():
        user_id = session.get('user_id')
        if user_id:
            user = User.query.get(user_id)
            if user:
                user.is_online = False
                user.last_seen = datetime.datetime.now(datetime.timezone.utc)
                db.session.commit()
        session.clear()
        return redirect('/auth/login')

    # Create tables if they don't exist (development convenience)
    with app.app_context():
        db.create_all()

    return app
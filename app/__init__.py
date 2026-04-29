# app/__init__.py
import os
from flask import Flask, redirect, session, render_template
from flask_cors import CORS
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from authlib.integrations.flask_client import OAuth
import datetime



oauth = OAuth()
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()



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

        # Database - fix the path
        db_url = config['database']['url']
        if db_url.startswith('sqlite:///'):
            db_path = db_url.replace('sqlite:///', '')
            if not os.path.isabs(db_path):
                db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), db_path)
            db_url = f'sqlite:///{db_path}'

        app.config['SQLALCHEMY_DATABASE_URI'] = db_url
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

        print(f"✅ Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")

    except Exception as e:
        print(f"⚠️ Error loading config: {e}")
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'kiselgram.db')

    app.config['GOOGLE_CLIENT_ID'] = config['google']['client_id']
    app.config['GOOGLE_CLIENT_SECRET'] = config['google']['client_secret']

    # Initialize extensions
    oauth.init_app(app)

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
    from app.routes import auth, chats, spa, premium, files
    app.register_blueprint(auth.auth_bp)
    app.register_blueprint(chats.chats_bp)
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

    return app
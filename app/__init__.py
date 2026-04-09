from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import os
import secrets

load_dotenv()

db = SQLAlchemy()


def create_app():
    # Get the base directory of your project
    basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

    app = Flask(__name__,
                template_folder=os.path.join(basedir, 'templates'),
                static_folder=os.path.join(basedir, 'static'))

    # Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'kiselgram-mobile-optimized-' + secrets.token_hex(16))
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///kiselgram.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # App metadata
    app.config['APP_NAME'] = os.getenv('APP_NAME', 'Kiselgram')
    app.config['VERSION'] = os.getenv('APP_VERSION', '2.0.0')
    app.config['ENV'] = os.getenv('FLASK_ENV', 'production')

    # File upload config
    app.config['UPLOAD_FOLDER'] = 'uploads'
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    app.config['ALLOWED_EXTENSIONS'] = {
        'images': {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'},
        'documents': {'pdf', 'doc', 'docx', 'txt', 'rtf'},
        'archives': {'zip', 'rar', '7z'},
        'media': {'mp3', 'mp4', 'm4a', 'wav', 'ogg', 'avi', 'mov', 'mkv'}
    }

    # Initialize extensions
    db.init_app(app)

    # Create upload directories
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'images'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'documents'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'media'), exist_ok=True)

    # Import models here to avoid circular imports
    from app import models

    # Register blueprints
    try:
        from app.routes.auth import auth_bp
        from app.routes.chats import chats_bp
        from app.routes.files import files_bp
        from app.routes.video_integration import video_int_bp
        from app.routes.utils_api import utils_api_bp  # New utility API
        from app.routes.spa_app import register_spa_bp
        app.register_blueprint(auth_bp)
        app.register_blueprint(chats_bp)
        app.register_blueprint(files_bp)
        app.register_blueprint(video_int_bp)
        app.register_blueprint(utils_api_bp)  # Register utility API
        register_spa_bp(app)


        print("✅ All blueprints registered successfully")
        print("✅ Utility API available at /api/utils")
        # CHANGE VERSION HERE
        # TODO: change version here before commit
        app.config['VERSION'] = '3.6.0'

    except ImportError as e:
        print(f"❌ Error importing blueprints: {e}")

    # Register template filter
    try:
        from app.utils.helpers import highlight_text
        app.jinja_env.filters['highlight_text'] = highlight_text
    except ImportError:
        print("⚠️ Warning: highlight_text filter not available")

    # Add context processor for templates
    @app.context_processor
    def utility_processor():
        try:
            from app.utils.helpers import get_current_user, get_current_user_id
            return {
                'current_user': get_current_user(),
                'session': {'user_id': get_current_user_id()},
                'app_version': app.config.get('VERSION', '2.0.0'),
                'app_name': app.config.get('APP_NAME', 'Kiselgram')
            }
        except ImportError:
            return {
                'current_user': None,
                'session': {'user_id': None},
                'app_version': app.config.get('VERSION', '2.0.0'),
                'app_name': app.config.get('APP_NAME', 'Kiselgram')
            }

    return app

if __name__ == '__main__':
    flask = create_app()
    flask.run()
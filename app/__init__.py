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
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'kiselgram-mobile-optimized-' + secrets.token_hex(16))
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///kiselgram.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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

    # Register blueprints - IMPORTANT: Import inside create_app to avoid circular imports
    try:
        from app.routes.auth import auth_bp
        from app.routes.chats import chats_bp
        from app.routes.groups import groups_bp
        from app.routes.channels import channels_bp
        from app.routes.files import files_bp
        from app.routes.api import api_bp
        from app.routes.search import search_bp
        from app.routes.status import status_bp
        from app.routes.video_integration import video_int_bp # New

        app.register_blueprint(auth_bp)
        app.register_blueprint(chats_bp)
        app.register_blueprint(groups_bp)
        app.register_blueprint(channels_bp)
        app.register_blueprint(files_bp)
        app.register_blueprint(api_bp)
        app.register_blueprint(search_bp)
        app.register_blueprint(status_bp)
        app.register_blueprint(video_int_bp) # New

    except ImportError as e:
        print(f"Error importing blueprints: {e}")
        print("Make sure all route files exist in app/routes/")

    # Register template filter
    try:
        from app.utils.helpers import highlight_text
        app.jinja_env.filters['highlight_text'] = highlight_text
    except ImportError:
        print("Warning: highlight_text filter not available")


    return app
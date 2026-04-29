from .auth import spa_auth_bp
from .chat import spa_chat_bp
from .groups import spa_groups_bp
from .channels import spa_channels_bp
from .contacts import spa_contacts_bp
from .stories import spa_stories_bp
from .profile import spa_profile_bp
from .calls import spa_calls_bp
from .search import spa_search_bp
from .favorites import spa_favorites_bp
from .sessions import spa_sessions_bp
from .messages import spa_messages_bp

def register_spa_blueprints(app):
    app.register_blueprint(spa_auth_bp)
    app.register_blueprint(spa_chat_bp)
    app.register_blueprint(spa_groups_bp)
    app.register_blueprint(spa_channels_bp)
    app.register_blueprint(spa_contacts_bp)
    app.register_blueprint(spa_stories_bp)
    app.register_blueprint(spa_profile_bp)
    app.register_blueprint(spa_calls_bp)
    app.register_blueprint(spa_search_bp)
    app.register_blueprint(spa_favorites_bp)
    app.register_blueprint(spa_sessions_bp)
    app.register_blueprint(spa_messages_bp)
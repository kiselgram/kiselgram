"""
Utility functions for Kiselgram application.
"""

from .helpers import (
    hash_password,
    get_current_user,
    get_current_user_id,
    generate_invite_link,
    allowed_file,
    get_file_type,
    create_thumbnail,
    format_file_size,
    highlight_text
)

from .bot_utils import (
    setup_bots,
    simulate_bot_interaction
)
from .email import send_email, send_welcome_email, send_verification_email, send_password_reset_email, confirm_password_reset_token, confirm_verification_token, generate_verification_token, generate_password_reset_token

# You can also add any initialization code here
__all__ = [
    # From helpers
    'hash_password',
    'get_current_user',
    'get_current_user_id',
    'generate_invite_link',
    'allowed_file',
    'get_file_type',
    'create_thumbnail',
    'format_file_size',
    'highlight_text',

    # From bot_utils
    'setup_bots',
    'simulate_bot_interaction',

    # from email
    'send_password_reset_email',
    'send_welcome_email',
    'send_email',
    'send_verification_email',
    'generate_password_reset_token',
    'generate_verification_token',
    'confirm_password_reset_token',
    'confirm_verification_token'

]
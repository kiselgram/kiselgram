# app/utils/email.py
"""Email utilities for Kiselgram - Gmail SMTP with templates"""

from flask import current_app, url_for, render_template
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
import os
import logging

mail = Mail()
logger = logging.getLogger(__name__)


def init_mail(app):
    """Initialize Flask-Mail with app config"""

    # Try to load from TOML config first
    try:
        import tomli
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'config', 'kis.toml'
        )
        if os.path.exists(config_path):
            with open(config_path, 'rb') as f:
                config = tomli.load(f)

            if 'email' in config:
                email_config = config['email']
                app.config['MAIL_SERVER'] = email_config.get('server', 'smtp.gmail.com')
                app.config['MAIL_PORT'] = email_config.get('port', 587)
                app.config['MAIL_USE_TLS'] = email_config.get('use_tls', True)
                app.config['MAIL_USERNAME'] = email_config.get('username')
                app.config['MAIL_PASSWORD'] = email_config.get('password')
                app.config['MAIL_DEFAULT_SENDER'] = email_config.get('sender', email_config.get('username'))

                logger.info(f"Email configured: {app.config['MAIL_USERNAME']}")
    except Exception as e:
        logger.warning(f"Could not load email config from TOML: {e}")

    mail.init_app(app)


def generate_verification_token(email):
    """Generate a verification token for email (24h expiry)"""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt='email-verification')


def confirm_verification_token(token, expiration=86400):
    """Confirm verification token"""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(token, salt='email-verification', max_age=expiration)
        return email
    except:
        return False


def generate_password_reset_token(email):
    """Generate password reset token (1h expiry)"""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt='password-reset')


def confirm_password_reset_token(token, expiration=3600):
    """Confirm password reset token"""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(token, salt='password-reset', max_age=expiration)
        return email
    except:
        return False


def send_email(to, subject, template_name, **kwargs):
    """Send an email using a template"""
    if not current_app.config.get('MAIL_USERNAME'):
        logger.error("Email not configured")
        return False

    try:
        html_content = render_template(f'email/{template_name}.html', **kwargs)

        msg = Message(
            subject=subject,
            recipients=[to] if isinstance(to, str) else to,
            html=html_content
        )
        mail.send(msg)
        logger.info(f"Email sent to {to}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {e}")
        return False


def send_verification_email(user_email, username):
    """Send verification email to user"""
    token = generate_verification_token(user_email)
    verify_url = url_for('auth.verify_email', token=token, _external=True)

    return send_email(
        to=user_email,
        subject='Verify Your Email - Kiselgram',
        template_name='verification',
        username=username,
        verify_url=verify_url
    )


def send_welcome_email(user_email, username):
    """Send welcome email after verification"""
    return send_email(
        to=user_email,
        subject='Welcome to Kiselgram! 🎉',
        template_name='welcome',
        username=username,
        app_url=url_for('chats.chat_list', _external=True),
        premium_url=url_for('premium.premium_page', _external=True)
    )


def send_password_reset_email(user_email, username):
    """Send password reset email"""
    token = generate_password_reset_token(user_email)
    reset_url = url_for('auth.reset_password', token=token, _external=True)

    return send_email(
        to=user_email,
        subject='Reset Your Password - Kiselgram',
        template_name='password_reset',
        username=username,
        reset_url=reset_url
    )
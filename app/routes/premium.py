# app/routes/premium.py
# Kiselgram Premium Management - Orange & Lime

import os
import json
import secrets
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from app import db
from app.models import User
from app.utils.helpers import get_current_user_id, get_current_user
import re
import time

premium_bp = Blueprint('premium', __name__, url_prefix='/premium')

# Path to premium config
PREMIUM_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'premium.toml')

# Premium price (monthly) - in RUB
PREMIUM_PRICE_MONTHLY = 300
PREMIUM_PRICE_YEARLY = 2990  # Save ~17%

PREMIUM_FEATURES = {
    'fonts': True,
    'stories': True,
    'wallpapers': True,
    'animated_stickers': True,
    'video_avatars': True,
    'chat_statistics': True,
    'custom_notifications': True,
    'increased_upload_limit': 500 * 1024 * 1024,  # 500MB
    'bot_api_access': True,
    'priority_support': True
}


# ============ CONFIG MANAGEMENT ============

def load_premium_config():
    """Load premium configuration from TOML file"""
    try:
        import tomli
        if os.path.exists(PREMIUM_CONFIG_PATH):
            with open(PREMIUM_CONFIG_PATH, 'rb') as f:
                return tomli.load(f)
    except ImportError:
        # Fallback to JSON if tomli not available
        json_path = PREMIUM_CONFIG_PATH.replace('.toml', '.json')
        if os.path.exists(json_path):
            with open(json_path, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading premium config: {e}")

    return {'promo_codes': {}, 'settings': {}}


def save_premium_config(config):
    """Save premium configuration to TOML file"""
    try:
        import tomli_w
        with open(PREMIUM_CONFIG_PATH, 'wb') as f:
            tomli_w.dump(config, f)
        return True
    except ImportError:
        # Fallback to JSON
        json_path = PREMIUM_CONFIG_PATH.replace('.toml', '.json')
        with open(json_path, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving premium config: {e}")
        return False


def generate_promo_code(duration_days=30, max_uses=1, created_by=None):
    """Generate a new promo code"""
    code = f"KISEL-{secrets.token_urlsafe(4).upper()}-{secrets.token_urlsafe(4).upper()}"

    config = load_premium_config()

    config['promo_codes'][code] = {
        'duration_days': duration_days,
        'max_uses': max_uses,
        'used_count': 0,
        'created_at': datetime.utcnow().isoformat(),
        'created_by': created_by,
        'expires_at': (datetime.utcnow() + timedelta(days=365)).isoformat(),
        'active': True
    }

    save_premium_config(config)
    return code


def has_premium_feature(user_id, feature):
    """Check if user has access to a premium feature"""
    user = User.query.get(user_id)
    if not user or not getattr(user, 'is_premium', False):
        return False
    return PREMIUM_FEATURES.get(feature, False)


def get_upload_limit(user_id):
    """Get max upload size for user"""
    if has_premium_feature(user_id, 'increased_upload_limit'):
        return PREMIUM_FEATURES['increased_upload_limit']
    return 100 * 1024 * 1024  # 100MB for free users


# ============ PAGE ROUTES ============

@premium_bp.route('/')
def premium_page():
    """Premium landing page"""
    user = get_current_user()
    if not user:
        return redirect(url_for('auth.login'))

    is_premium = getattr(user, 'is_premium', False)
    premium_expires = getattr(user, 'premium_expires_at', None)

    return render_template('premium/index.html',
                           user=user,
                           is_premium=is_premium,
                           premium_expires=premium_expires,
                           price=PREMIUM_PRICE_MONTHLY,
                           price_yearly=PREMIUM_PRICE_YEARLY,
                           features=PREMIUM_FEATURES)


@premium_bp.route('/success')
def success_page():
    """Premium activation success page"""
    user = get_current_user()
    if not user:
        return redirect(url_for('auth.login'))
    return render_template('premium/success.html', user=user)


# ============ API ROUTES ============

@premium_bp.route('/api/check/<int:user_id>')
def api_check_premium(user_id):
    """Check if user has premium"""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404

        is_premium = getattr(user, 'is_premium', False)
        expires_at = getattr(user, 'premium_expires_at', None)

        # Check if premium has expired
        if is_premium and expires_at and datetime.utcnow() > expires_at:
            user.is_premium = False
            db.session.commit()
            is_premium = False
            expires_at = None

        return jsonify({
            'success': True,
            'is_premium': is_premium,
            'premium_expires_at': expires_at.isoformat() if expires_at else None,
            'features': PREMIUM_FEATURES if is_premium else {}
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@premium_bp.route('/api/features')
def api_get_features():
    """Get premium features status for current user"""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    user = User.query.get(user_id)
    is_premium = getattr(user, 'is_premium', False)

    return jsonify({
        'success': True,
        'is_premium': is_premium,
        'features': PREMIUM_FEATURES if is_premium else {},
        'upload_limit': get_upload_limit(user_id)
    })


@premium_bp.route('/api/validate-promo', methods=['POST'])
def api_validate_promo():
    """Validate a promo code"""
    try:
        data = request.get_json()
        code = data.get('code', '').strip().upper()

        if not code:
            return jsonify({'success': False, 'error': 'Enter promo code'}), 400

        config = load_premium_config()

        if code not in config.get('promo_codes', {}):
            return jsonify({'success': False, 'error': 'Invalid promo code'}), 400

        promo = config['promo_codes'][code]

        if not promo.get('active', True):
            return jsonify({'success': False, 'error': 'Inactive promo'}), 400

        if promo.get('used_count', 0) >= promo.get('max_uses', 1):
            return jsonify({'success': False, 'error': 'Max uses reached'}), 400

        if 'expires_at' in promo:
            expires_at = datetime.fromisoformat(promo['expires_at'])
            if datetime.utcnow() > expires_at:
                return jsonify({'success': False, 'error': 'Promo expired'}), 400

        return jsonify({
            'success': True,
            'valid': True,
            'duration_days': promo.get('duration_days', 30),
            'message': f"Valid for {promo.get('duration_days', 30)} days!"
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@premium_bp.route('/api/activate', methods=['POST'])
def api_activate_premium():
    """Activate premium for current user"""
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        user = User.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404

        data = request.get_json()
        plan = data.get('plan', 'monthly')
        promo_code = data.get('promo_code', '').strip().upper()

        duration_days = 365 if plan == 'yearly' else 30

        if promo_code:
            config = load_premium_config()
            if promo_code in config.get('promo_codes', {}):
                promo = config['promo_codes'][promo_code]
                if promo.get('active', True) and promo.get('used_count', 0) < promo.get('max_uses', 1):
                    duration_days = promo.get('duration_days', 30)
                    config['promo_codes'][promo_code]['used_count'] = promo.get('used_count', 0) + 1
                    save_premium_config(config)

        now = datetime.utcnow()
        user.is_premium = True
        user.premium_since = now if not user.premium_since else user.premium_since
        user.premium_expires_at = now + timedelta(days=duration_days)
        user.premium_plan = plan
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Premium activated for {duration_days} days!',
            'expires_at': user.premium_expires_at.isoformat(),
            'features': PREMIUM_FEATURES
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@premium_bp.route('/api/cancel', methods=['POST'])
def api_cancel_premium():
    """Cancel premium auto-renewal"""
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        user = User.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404

        user.premium_auto_renew = False
        db.session.commit()

        return jsonify({'success': True, 'message': 'Premium auto-renewal cancelled'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ ADMIN ROUTES ============

@premium_bp.route('/admin/generate-promo', methods=['POST'])
def admin_generate_promo():
    """Admin: Generate a new promo code"""
    try:
        user = get_current_user()
        if not user or not getattr(user, 'is_admin', False):
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403

        data = request.get_json()
        duration_days = data.get('duration_days', 30)
        max_uses = data.get('max_uses', 1)
        custom_code = data.get('custom_code')

        config = load_premium_config()

        if custom_code:
            code = custom_code.upper()
        else:
            code = f"KISEL-{secrets.token_urlsafe(4).upper()}-{secrets.token_urlsafe(4).upper()}"

        if 'promo_codes' not in config:
            config['promo_codes'] = {}

        if code in config['promo_codes']:
            return jsonify({'success': False, 'error': 'Code already exists'}), 400

        config['promo_codes'][code] = {
            'duration_days': duration_days,
            'max_uses': max_uses,
            'used_count': 0,
            'created_at': datetime.utcnow().isoformat(),
            'created_by': user.username,
            'expires_at': (datetime.utcnow() + timedelta(days=365)).isoformat(),
            'active': True
        }

        save_premium_config(config)

        return jsonify({
            'success': True,
            'code': code,
            'duration_days': duration_days,
            'max_uses': max_uses
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@premium_bp.route('/admin/promo-codes')
def admin_list_promos():
    """Admin: List all promo codes"""
    try:
        user = get_current_user()
        if not user or not getattr(user, 'is_admin', False):
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403

        config = load_premium_config()
        promos = []

        for code, data in config.get('promo_codes', {}).items():
            promos.append({
                'code': code,
                'duration_days': data.get('duration_days', 30),
                'used_count': data.get('used_count', 0),
                'max_uses': data.get('max_uses', 1),
                'active': data.get('active', True),
                'created_at': data.get('created_at'),
                'expires_at': data.get('expires_at')
            })

        return jsonify({'success': True, 'promo_codes': promos})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@premium_bp.route('/admin/toggle-promo/<code>', methods=['POST'])
def admin_toggle_promo(code):
    """Admin: Toggle promo code active status"""
    try:
        user = get_current_user()
        if not user or not getattr(user, 'is_admin', False):
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403

        config = load_premium_config()

        if code in config.get('promo_codes', {}):
            config['promo_codes'][code]['active'] = not config['promo_codes'][code].get('active', True)
            save_premium_config(config)
            return jsonify({
                'success': True,
                'active': config['promo_codes'][code]['active']
            })

        return jsonify({'success': False, 'error': 'Promo code not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ TEMPLATE FILTERS ============

@premium_bp.app_template_filter('format_date')
def format_date_filter(date):
    """Format date for templates"""
    if not date:
        return 'N/A'
    return date.strftime('%B %d, %Y')


@premium_bp.app_template_filter('time_until')
def time_until_filter(date):
    """Format time until expiration"""
    if not date:
        return 'N/A'

    now = datetime.utcnow()
    if date < now:
        return 'Expired'

    delta = date - now
    days = delta.days

    if days > 30:
        months = days // 30
        return f"{months} month{'s' if months != 1 else ''}"
    elif days > 0:
        return f"{days} day{'s' if days != 1 else ''}"
    else:
        hours = delta.seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''}"


# ============ ANIMATED STICKERS ============

# Path to Kisel emojis
KISEL_EMOJI_PATH = os.path.expanduser('~/Desktop/kisel_bottle_emojis/compressed')


@premium_bp.route('/api/stickers')
def api_get_stickers():
    """Get premium animated stickers from local Kisel emojis"""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    if not has_premium_feature(user_id, 'animated_stickers'):
        return jsonify({'success': False, 'error': 'Premium required', 'upgrade_url': '/premium'}), 403

    stickers = []

    # Load stickers from desktop folder
    if os.path.exists(KISEL_EMOJI_PATH):
        import re
        pattern = re.compile(r'kisel_(.+?)_\d{10}\.png')

        for filename in os.listdir(KISEL_EMOJI_PATH):
            if filename.endswith('.png'):
                match = pattern.match(filename)
                if match:
                    unicode_repr = match.group(1)
                    # Convert unicode representation to actual emoji
                    try:
                        # Handle format like 'U+1F600'
                        if unicode_repr.startswith('U+'):
                            code_point = int(unicode_repr[2:], 16)
                            emoji = chr(code_point)
                        else:
                            emoji = unicode_repr
                    except:
                        emoji = '📸'

                    stickers.append({
                        'id': filename.replace('.png', ''),
                        'url': f'/premium/sticker/{filename}',
                        'emoji': emoji,
                        'name': f'Kisel {emoji}'
                    })

    # Group into packs
    packs = []
    if stickers:
        # Split into packs of 6 stickers each
        pack_size = 6
        for i in range(0, len(stickers), pack_size):
            pack_stickers = stickers[i:i + pack_size]
            pack_number = i // pack_size + 1
            packs.append({
                'id': f'kisel_pack_{pack_number}',
                'name': f'Kisel Pack {pack_number}',
                'icon': pack_stickers[0]['emoji'] if pack_stickers else '🍊',
                'stickers': pack_stickers
            })

    # If no local stickers found, provide fallback
    if not packs:
        packs = [{
            'id': 'default',
            'name': 'Kisel Emojis',
            'icon': '🍊',
            'stickers': [
                {'id': '1', 'url': '/static/stickers/default1.png', 'emoji': '😊'},
                {'id': '2', 'url': '/static/stickers/default2.png', 'emoji': '❤️'},
            ]
        }]

    return jsonify({'success': True, 'stickers': {'packs': packs}})


@premium_bp.route('/sticker/<filename>')
def serve_sticker(filename):
    """Serve sticker file from desktop folder"""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401

    if not has_premium_feature(user_id, 'animated_stickers'):
        return jsonify({'error': 'Premium required'}), 403

    # Security: only allow png files
    if not filename.endswith('.png'):
        return jsonify({'error': 'Invalid file'}), 400

    # Prevent directory traversal
    filename = os.path.basename(filename)
    file_path = os.path.join(KISEL_EMOJI_PATH, filename)

    if not os.path.exists(file_path):
        return jsonify({'error': 'Sticker not found'}), 404

    from flask import send_file
    return send_file(file_path, mimetype='image/png')


# Add these endpoints to app/routes/premium.py



@premium_bp.route('/api/bot/<token>/updates', methods=['GET'])
def bot_get_updates(token):
    """Get new messages for bot (long polling)"""
    from app.models import User, Message

    bot = User.query.filter_by(bot_token=token, is_bot=True).first()
    if not bot:
        return jsonify({'success': False, 'error': 'Invalid bot token'}), 401

    after_id = request.args.get('after_id', 0, type=int)
    timeout = request.args.get('timeout', 30, type=int)

    # Wait for new messages (simple long polling)
    start_time = datetime.utcnow()

    while (datetime.utcnow() - start_time).total_seconds() < timeout:
        # Get messages sent to this bot
        messages = Message.query.filter(
            Message.receiver_id == bot.id,
            Message.id > after_id
        ).order_by(Message.id.asc()).all()

        if messages:
            updates = []
            for msg in messages:
                updates.append({
                    'message': {
                        'id': msg.id,
                        'chat_id': msg.sender_id,  # Reply to sender
                        'sender_id': msg.sender_id,
                        'content': msg.content,
                        'timestamp': msg.timestamp.isoformat() if msg.timestamp else None,
                        'is_bot': False
                    }
                })

            return jsonify({'success': True, 'updates': updates})

        time.sleep(0.5)  # Wait before checking again

    # Timeout - no messages
    return jsonify({'success': True, 'updates': []})




def register_premium_bp(app):
    """Register premium blueprint with app"""
    app.register_blueprint(premium_bp)

    # Create premium.toml if it doesn't exist
    if not os.path.exists(PREMIUM_CONFIG_PATH):
        default_config = {
            'promo_codes': {},
            'settings': {
                'price_monthly': PREMIUM_PRICE_MONTHLY,
                'price_yearly': PREMIUM_PRICE_YEARLY,
                'trial_days': 7
            }
        }
        save_premium_config(default_config)
        print(f"Created premium.toml at {PREMIUM_CONFIG_PATH}")


# ============ BOT API ENDPOINTS ============

@premium_bp.route('/api/bot/create', methods=['POST'])
def api_create_bot():
    """Create a new bot"""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    # Check if user has premium
    if not has_premium_feature(user_id, 'bot_api_access'):
        return jsonify({'success': False, 'error': 'Premium required'}), 403

    data = request.get_json()
    bot_name = data.get('name', '').strip()
    bot_username = data.get('username', '').strip().lower()
    description = data.get('description', '').strip()

    if not bot_name or len(bot_name) < 3:
        return jsonify({'success': False, 'error': 'Bot name must be at least 3 characters'}), 400

    if not bot_username or not re.match(r'^[a-z0-9_]+$', bot_username):
        return jsonify(
            {'success': False, 'error': 'Username must be alphanumeric (lowercase) and underscores only'}), 400

    if len(bot_username) < 3:
        return jsonify({'success': False, 'error': 'Username must be at least 3 characters'}), 400

    # Check if username taken
    existing = User.query.filter_by(username=bot_username).first()
    if existing:
        return jsonify({'success': False, 'error': 'Username already taken'}), 400

    # Create bot user
    bot_token = secrets.token_urlsafe(32)

    bot_user = User(
        username=bot_username,
        display_name=bot_name,
        bio=description or f"Bot created by premium user",
        is_bot=True,
        bot_owner_id=user_id,
        bot_token=bot_token,
        created_at=datetime.utcnow()
    )
    # Set a random password for the bot account
    bot_user.set_password(secrets.token_urlsafe(32))

    db.session.add(bot_user)
    db.session.commit()

    return jsonify({
        'success': True,
        'bot': {
            'id': bot_user.id,
            'name': bot_name,
            'username': bot_username,
            'token': bot_token,
            'api_endpoint': f'/api/bot/{bot_token}'
        },
        'message': 'Bot created successfully!'
    })


@premium_bp.route('/api/bot/list')
def api_list_bots():
    """List user's bots"""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    bots = User.query.filter_by(bot_owner_id=user_id, is_bot=True).all()

    bot_list = [{
        'id': b.id,
        'name': b.display_name,
        'username': b.username,
        'created_at': b.created_at.isoformat() if b.created_at else None,
        'token': b.bot_token[:8] + '••••••••' if b.bot_token else None
    } for b in bots]

    return jsonify({'success': True, 'bots': bot_list})


@premium_bp.route('/api/bot/<int:bot_id>', methods=['DELETE'])
def api_delete_bot(bot_id):
    """Delete a bot"""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    bot = User.query.filter_by(id=bot_id, bot_owner_id=user_id, is_bot=True).first()

    if not bot:
        return jsonify({'success': False, 'error': 'Bot not found'}), 404

    db.session.delete(bot)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Bot deleted'})


@premium_bp.route('/api/bot/<int:bot_id>/regenerate-token', methods=['POST'])
def api_regenerate_bot_token(bot_id):
    """Regenerate bot token"""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    bot = User.query.filter_by(id=bot_id, bot_owner_id=user_id, is_bot=True).first()

    if not bot:
        return jsonify({'success': False, 'error': 'Bot not found'}), 404

    bot.bot_token = secrets.token_urlsafe(32)
    db.session.commit()

    return jsonify({
        'success': True,
        'token': bot.bot_token,
        'message': 'Token regenerated'
    })


@premium_bp.route('/api/bot/<token>/test', methods=['GET'])
def bot_test_connection(token):
    """Test bot connection"""
    bot = User.query.filter_by(bot_token=token, is_bot=True).first()
    if not bot:
        return jsonify({'success': False, 'error': 'Invalid bot token'}), 401

    return jsonify({
        'success': True,
        'bot_name': bot.display_name,
        'bot_username': bot.username,
        'owner_id': bot.bot_owner_id
    })


@premium_bp.route('/api/bot/<token>/send', methods=['POST'])
def bot_send_message(token):
    """Send a message as the bot"""
    bot = User.query.filter_by(bot_token=token, is_bot=True).first()
    if not bot:
        return jsonify({'success': False, 'error': 'Invalid bot token'}), 401

    # Check if owner still has premium
    if not has_premium_feature(bot.bot_owner_id, 'bot_api_access'):
        return jsonify({'success': False, 'error': 'Bot owner no longer has premium'}), 403

    data = request.get_json()
    chat_id = data.get('chat_id')
    content = data.get('content', '').strip()

    if not chat_id or not content:
        return jsonify({'success': False, 'error': 'chat_id and content required'}), 400

    # Create message
    from app.models import Message
    message = Message(
        sender_id=bot.id,
        receiver_id=chat_id,
        content=content,
        timestamp=datetime.utcnow()
    )

    db.session.add(message)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': {
            'id': message.id,
            'content': content,
            'timestamp': message.timestamp.isoformat()
        }
    })


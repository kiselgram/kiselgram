# app/routes/premium.py
# Kiselgram Premium Management - Orange & Lime

import os
import uuid
import json
import secrets
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
from app import db
from app.models import User
from app.utils.helpers import get_current_user_id, get_current_user

premium_bp = Blueprint('premium', __name__, url_prefix='/premium')

# Path to premium config
PREMIUM_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'premium.toml')

# Premium price (monthly)
PREMIUM_PRICE = 4.99


# ============ PROMO CODE MANAGEMENT ============

def load_premium_config():
    """Load premium configuration from TOML file"""

    import tomli
    if os.path.exists(PREMIUM_CONFIG_PATH):
        with open(PREMIUM_CONFIG_PATH, 'rb') as file:
            return tomli.load(file)

    return {'promo_codes': {}, 'settings': {}}


def save_premium_config(config):
    """Save premium configuration to TOML file"""
    try:
        import toml
        with open(PREMIUM_CONFIG_PATH, 'w') as f:
            toml.dump(config, f)
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


def validate_promo_code(code):
    """Validate a promo code"""
    config = load_premium_config()

    if code not in config['promo_codes']:
        return {'valid': False, 'error': 'Invalid promo code'}

    promo = config['promo_codes'][code]

    # Check if active
    if not promo.get('active', True):
        return {'valid': False, 'error': 'Promo code is inactive'}

    # Check expiration
    if 'expires_at' in promo:
        expires_at = datetime.fromisoformat(promo['expires_at'])
        if datetime.utcnow() > expires_at:
            return {'valid': False, 'error': 'Promo code has expired'}

    # Check uses
    if promo['used_count'] >= promo.get('max_uses', 1):
        return {'valid': False, 'error': 'Promo code has reached maximum uses'}

    return {
        'valid': True,
        'duration_days': promo['duration_days'],
        'code': code
    }


def use_promo_code(code, user_id):
    """Mark a promo code as used"""
    config = load_premium_config()

    if code in config['promo_codes']:
        config['promo_codes'][code]['used_count'] += 1
        config['promo_codes'][code]['used_by'] = config['promo_codes'][code].get('used_by', [])
        config['promo_codes'][code]['used_by'].append({
            'user_id': user_id,
            'used_at': datetime.utcnow().isoformat()
        })
        save_premium_config(config)
        return True

    return False


# ============ AUTO-RELOAD CONFIG ============

# Store last loaded time
_last_config_load = datetime.utcnow()
_config_cache = None


def get_cached_config():
    """Get cached config, reload every 25 seconds"""
    global _last_config_load, _config_cache

    now = datetime.utcnow()
    if _config_cache is None or (now - _last_config_load).total_seconds() > 25:
        _config_cache = load_premium_config()
        _last_config_load = now
        print(f"🔄 Premium config reloaded at {now}")

    return _config_cache


# ============ PREMIUM PAGES ============

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
                           price=PREMIUM_PRICE)


@premium_bp.route('/upgrade')
def upgrade_page():
    """Upgrade to premium page"""
    user = get_current_user()
    if not user:
        return redirect(url_for('auth.login'))

    return render_template('premium/upgrade.html',
                           user=user,
                           price=PREMIUM_PRICE)


@premium_bp.route('/success')
def success_page():
    """Premium activation success page"""
    user = get_current_user()
    if not user:
        return redirect(url_for('auth.login'))

    return render_template('premium/success.html', user=user)


# ============ API ENDPOINTS ============

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
        if is_premium and expires_at:
            if datetime.utcnow() > expires_at:
                user.is_premium = False
                db.session.commit()
                is_premium = False
                expires_at = None

        return jsonify({
            'success': True,
            'is_premium': is_premium,
            'premium_expires_at': expires_at.isoformat() if expires_at else None,
            'premium_since': user.premium_since.isoformat() if getattr(user, 'premium_since', None) else None
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@premium_bp.route('/api/validate-promo', methods=['POST'])
def api_validate_promo():
    """Validate a promo code"""
    try:
        data = request.get_json()
        code = data.get('code', '').strip().upper()

        if not code:
            return jsonify({'success': False, 'error': 'Please enter a promo code'}), 400

        # Use cached config (reloads every 25s)
        config = get_cached_config()

        if code not in config.get('promo_codes', {}):
            return jsonify({'success': False, 'error': 'Invalid promo code'})

        promo = config['promo_codes'][code]

        # Check if active
        if not promo.get('active', True):
            return jsonify({'success': False, 'error': 'Promo code is inactive'})

        # Check expiration
        if 'expires_at' in promo:
            expires_at = datetime.fromisoformat(promo['expires_at'])
            if datetime.utcnow() > expires_at:
                return jsonify({'success': False, 'error': 'Promo code has expired'})

        # Check uses
        if promo['used_count'] >= promo.get('max_uses', 1):
            return jsonify({'success': False, 'error': 'Promo code has reached maximum uses'})

        return jsonify({
            'success': True,
            'valid': True,
            'duration_days': promo['duration_days'],
            'message': f"Valid for {promo['duration_days']} days of Kiselgram Premium!"
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
        payment_method = data.get('payment_method', 'card')
        promo_code = data.get('promo_code', '').strip().upper()

        duration_days = 30  # Default 30 days

        # Check for promo code
        if promo_code:
            validation = validate_promo_code(promo_code)
            if validation['valid']:
                duration_days = validation['duration_days']
                use_promo_code(promo_code, user_id)
            else:
                return jsonify({'success': False, 'error': validation['error']}), 400

        # Calculate expiration
        now = datetime.utcnow()
        expires_at = now + timedelta(days=duration_days)

        # Update user premium status
        user.is_premium = True
        user.premium_since = now if not user.premium_since else user.premium_since
        user.premium_expires_at = expires_at
        user.premium_payment_method = payment_method

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Premium activated! Enjoy Kiselgram Premium for {duration_days} days!',
            'expires_at': expires_at.isoformat(),
            'duration_days': duration_days
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error activating premium: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@premium_bp.route('/api/cancel', methods=['POST'])
def api_cancel_premium():
    """Cancel premium subscription"""
    try:
        user_id = get_current_user_id()
        if not user_id:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401

        user = User.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'error': 'User not found'}), 404

        # Don't remove immediately, let it expire
        # Just mark for cancellation
        user.premium_auto_renew = False

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Premium subscription cancelled. Your premium will remain active until expiration.'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ ADMIN ENDPOINTS ============

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

        code = generate_promo_code(
            duration_days=duration_days,
            max_uses=max_uses,
            created_by=user.username
        )

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

        config = get_cached_config()
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


def register_premium_bp(app):
    """Register premium blueprint with app"""
    app.register_blueprint(premium_bp)

    # Create premium.toml if it doesn't exist
    if not os.path.exists(PREMIUM_CONFIG_PATH):
        default_config = {
            'promo_codes': {},
            'settings': {
                'price_monthly': 4.99,
                'price_yearly': 49.99,
                'trial_days': 7
            }
        }
        save_premium_config(default_config)
        print(f"🍊 Created premium.toml at {PREMIUM_CONFIG_PATH}")
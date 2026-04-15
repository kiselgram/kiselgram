# app/routes/chats.py

from flask import Blueprint, render_template, redirect, url_for, session, request
from app.models import User
from app.utils.helpers import get_current_user

chats_bp = Blueprint('chats', __name__)


def is_mobile_device():
    """Detect if request is from mobile device"""
    ua = request.user_agent.string.lower()
    mobile_keywords = ['mobile', 'android', 'iphone', 'ipad', 'ipod', 'blackberry', 'windows phone']
    return any(keyword in ua for keyword in mobile_keywords)


def get_template(user, template_type):
    """Get appropriate template based on device and premium status"""
    session_mobile = session.get('is_mobile')
    is_mobile = session_mobile if session_mobile is not None else is_mobile_device()

    is_premium = getattr(user, 'is_premium', False) if user else False

    if is_premium:
        return 'prem-mob.html' if is_mobile else 'prem-desk.html'
    else:
        return 'free-mob.html' if is_mobile else 'free-desk.html'


@chats_bp.route('/')
def index():
    """Root route - redirects to appropriate version"""
    user = get_current_user()
    if not user:
        return redirect(url_for('auth.login'))

    template = get_template(user, 'main')
    return render_template(template, current_user=user)


@chats_bp.route('/chat_list')
def chat_list():
    """Main chat list"""
    user = get_current_user()
    if not user:
        return redirect(url_for('auth.login'))

    template = get_template(user, 'main')
    return render_template(template, current_user=user)


@chats_bp.route('/prem-mob')
def prem_mob():
    """Premium mobile version"""
    user = get_current_user()
    if not user:
        return redirect(url_for('auth.login'))
    session['is_mobile'] = True
    return render_template('prem-mob.html', current_user=user, is_premium=True)


@chats_bp.route('/prem-desk')
def prem_desk():
    """Premium desktop version"""
    user = get_current_user()
    if not user:
        return redirect(url_for('auth.login'))
    session['is_mobile'] = False
    return render_template('prem-desk.html', current_user=user, is_premium=True)


@chats_bp.route('/free-mob')
def free_mob():
    """Free mobile version"""
    user = get_current_user()
    if not user:
        return redirect(url_for('auth.login'))
    session['is_mobile'] = True
    return render_template('free-mob.html', current_user=user, is_premium=False)


@chats_bp.route('/free-desk')
def free_desk():
    """Free desktop version"""
    user = get_current_user()
    if not user:
        return redirect(url_for('auth.login'))
    session['is_mobile'] = False
    return render_template('free-desk.html', current_user=user, is_premium=False)


@chats_bp.route('/mob-reg')
def mob_register():
    """Set mobile session"""
    session['is_mobile'] = True
    return redirect(url_for('chats.chat_list'))


@chats_bp.route('/desk-reg')
def desk_register():
    """Set desktop session"""
    session['is_mobile'] = False
    return redirect(url_for('chats.chat_list'))


@chats_bp.route('/kis_info')
def kis_info():
    """About page"""
    user = get_current_user()
    return render_template('kis_info.html', current_user=user)
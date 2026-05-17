from flask import Blueprint, request, jsonify
from sqlalchemy import or_

from app import db
from app.models import User, Group, Channel, Message, RecentSearch
from app.utils.helpers import get_current_user_id

spa_search_bp = Blueprint('spa_search', __name__, url_prefix='/api')

@spa_search_bp.route('/search/global', methods=['GET'])
def global_search():
    """Search users, groups, and channels by query string."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify({'success': True, 'results': {'users': [], 'groups': [], 'channels': []}})

    # Users
    users = User.query.filter(
        User.id != user_id,
        or_(User.username.ilike(f'%{query}%'), User.display_name.ilike(f'%{query}%'))
    ).limit(20).all()

    # Groups (public only, or ones user is member of)
    user_group_ids = [gm.group_id for gm in Group.members.filter(Group.members.any(user_id=user_id)).all()] if False else []
    # For simplicity, show public groups only
    groups = Group.query.filter(Group.is_public == True, Group.name.ilike(f'%{query}%')).limit(20).all()

    # Channels (public)
    channels = Channel.query.filter(Channel.is_public == True, Channel.name.ilike(f'%{query}%')).limit(20).all()

    # Save recent search
    recent = RecentSearch(user_id=user_id, search_query=query, search_type='all')
    db.session.add(recent)
    db.session.commit()

    return jsonify({
        'success': True,
        'results': {
            'users': [{'id': u.id, 'username': u.username, 'display_name': u.display_name or u.username,
                        'avatar_url': u.avatar_url, 'is_online': u.is_online} for u in users],
            'groups': [{'id': g.id, 'name': g.name, 'description': g.description, 'member_count': GroupMember.query.filter_by(group_id=g.id).count(),
                         'is_public': g.is_public, 'invite_link': g.invite_link} for g in groups],
            'channels': [{'id': c.id, 'name': c.name, 'description': c.description, 'subscriber_count': ChannelSubscriber.query.filter_by(channel_id=c.id).count(),
                          'is_public': c.is_public, 'invite_link': c.invite_link} for c in channels]
        }
    })

@spa_search_bp.route('/recent_searches', methods=['GET'])
def recent_searches():
    """Return the last 10 unique recent searches of the current user."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    searches = db.session.query(RecentSearch.search_query, RecentSearch.search_type,
                                 db.func.max(RecentSearch.created_at).label('last')).\
        filter_by(user_id=user_id).\
        group_by(RecentSearch.search_query).\
        order_by(db.desc('last')).limit(10).all()

    return jsonify([{'query': s[0], 'type': s[1], 'last_searched': s[2].isoformat()} for s in searches])

@spa_search_bp.route('/search_in_chat', methods=['POST'])
def search_in_chat():
    """Search messages in a specific chat by keyword."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    data = request.get_json()
    chat_id = data.get('chat_id')
    query = data.get('query', '').strip()

    if not chat_id or len(query) < 2:
        return jsonify({'success': True, 'messages': []})

    messages = Message.query.filter(
        Message.chat_id == chat_id,
        Message.content.ilike(f'%{query}%'),
        Message.is_deleted == False
    ).order_by(Message.created_at.desc()).limit(100).all()

    results = []
    for msg in messages:
        results.append({
            'id': msg.id,
            'content': msg.content,
            'sender_id': msg.sender_id,
            'sender_name': msg.sender.username if msg.sender else 'Unknown',
            'timestamp': msg.created_at.isoformat(),
            'is_mine': msg.sender_id == user_id
        })
    return jsonify({'success': True, 'messages': results})
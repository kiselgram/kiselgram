from flask import Blueprint, request, jsonify
from app import db
from app.models import Favorite
from app.utils.helpers import get_current_user_id

spa_favorites_bp = Blueprint('spa_favorites', __name__, url_prefix='/api')

@spa_favorites_bp.route('/favorites', methods=['GET'])
def get_favorites():
    """Get all favorites of the current user."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    favs = Favorite.query.filter_by(user_id=user_id).order_by(Favorite.created_at.desc()).all()
    result = []
    for fav in favs:
        result.append({
            'id': fav.id,
            'file_type': fav.file_type,
            'file_path': fav.file_path,
            'file_name': fav.file_name,
            'note': fav.note,
            'created_at': fav.created_at.isoformat() if fav.created_at else None
        })
    return jsonify({'success': True, 'favorites': result})

@spa_favorites_bp.route('/favorites', methods=['POST'])
def add_favorite():
    """Add a new favorite item."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    data = request.get_json()
    fav = Favorite(
        user_id=user_id,
        file_type=data.get('file_type', 'document'),
        file_path=data.get('file_path'),
        file_name=data.get('file_name'),
        note=data.get('note', '')
    )
    db.session.add(fav)
    db.session.commit()
    return jsonify({'success': True, 'favorite_id': fav.id})

@spa_favorites_bp.route('/favorites/<int:fav_id>', methods=['DELETE'])
def delete_favorite(fav_id):
    """Delete a favorite item (only the owner can delete)."""
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    fav = Favorite.query.get_or_404(fav_id)
    if fav.user_id != user_id:
        return jsonify({'success': False, 'error': 'Not authorized'}), 403

    db.session.delete(fav)
    db.session.commit()
    return jsonify({'success': True})
from flask import Blueprint, request, jsonify
from app import db
from app.models import User, BlockedUser, Contact, ContactName
from app.utils.helpers import get_current_user_id, get_current_user

spa_contacts_bp = Blueprint('spa_contacts', __name__, url_prefix='/api')


def user_to_contact_dict(user, custom_name=None):
    return {
        'id': user.id,
        'username': user.username,
        'display_name': user.display_name or user.username,
        'avatar_url': user.avatar_url,
        'is_online': getattr(user, 'is_online', False),
        'last_seen': user.last_seen.isoformat() if user.last_seen else None,
        'custom_name': custom_name
    }


# ==================== CONTACTS ====================

@spa_contacts_bp.route('/contacts', methods=['GET'])
def get_contacts():
    """List all contacts of the current user, with custom names if set."""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    # Get contacts with custom names
    rows = db.session.query(Contact, ContactName).join(
        ContactName,
        (Contact.user_id == ContactName.user_id) & (Contact.contact_id == ContactName.contact_id),
        isouter=True
    ).filter(Contact.user_id == current_user_id).all()

    contacts = []
    for contact_rel, name_rel in rows:
        user = User.query.get(contact_rel.contact_id)
        if user and not user.is_deleted:
            contacts.append(user_to_contact_dict(user, custom_name=name_rel.name if name_rel else None))

    return jsonify({'success': True, 'contacts': contacts})


@spa_contacts_bp.route('/contacts', methods=['POST'])
def add_contact():
    """Add a user to contacts. If bidirectional, auto-add the current user to the other user's contacts."""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    data = request.get_json()
    contact_id = data.get('contact_id')
    if not contact_id or contact_id == current_user_id:
        return jsonify({'success': False, 'error': 'Invalid contact_id'}), 400

    # Check if already a contact
    existing = Contact.query.filter_by(user_id=current_user_id, contact_id=contact_id).first()
    if existing:
        return jsonify({'success': True, 'message': 'Already in contacts'})

    # Add contact
    new_contact = Contact(user_id=current_user_id, contact_id=contact_id)
    db.session.add(new_contact)

    # Auto-add reverse (optional – can be commented out if not desired)
    reverse = Contact.query.filter_by(user_id=contact_id, contact_id=current_user_id).first()
    if not reverse:
        db.session.add(Contact(user_id=contact_id, contact_id=current_user_id))

    db.session.commit()
    return jsonify({'success': True})


@spa_contacts_bp.route('/contacts/rename', methods=['POST'])
def rename_contact():
    """Set a custom name for a contact."""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    data = request.get_json()
    contact_id = data.get('contact_id')
    name = data.get('name', '').strip()
    if not contact_id:
        return jsonify({'success': False, 'error': 'contact_id required'}), 400

    # Check that the contact actually exists
    contact = Contact.query.filter_by(user_id=current_user_id, contact_id=contact_id).first()
    if not contact:
        return jsonify({'success': False, 'error': 'Contact not found'}), 404

    # Upsert custom name
    custom = ContactName.query.filter_by(user_id=current_user_id, contact_id=contact_id).first()
    if name:
        if custom:
            custom.name = name
        else:
            db.session.add(ContactName(user_id=current_user_id, contact_id=contact_id, name=name))
    else:
        # Empty name → remove custom name
        if custom:
            db.session.delete(custom)

    db.session.commit()
    return jsonify({'success': True})


# ==================== BLOCKING ====================

@spa_contacts_bp.route('/block_user/<int:user_id>', methods=['POST'])
def block_user(user_id):
    """Block a user."""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    if current_user_id == user_id:
        return jsonify({'success': False, 'error': 'Cannot block yourself'}), 400

    existing = BlockedUser.query.filter_by(user_id=current_user_id, blocked_user_id=user_id).first()
    if existing:
        return jsonify({'success': False, 'error': 'Already blocked'}), 400

    db.session.add(BlockedUser(user_id=current_user_id, blocked_user_id=user_id))
    db.session.commit()
    return jsonify({'success': True, 'message': 'User blocked'})


@spa_contacts_bp.route('/unblock_user/<int:user_id>', methods=['POST'])
def unblock_user(user_id):
    """Unblock a user."""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    BlockedUser.query.filter_by(user_id=current_user_id, blocked_user_id=user_id).delete()
    db.session.commit()
    return jsonify({'success': True, 'message': 'User unblocked'})


@spa_contacts_bp.route('/blocked_users', methods=['GET'])
def get_blocked_users():
    """List all users blocked by the current user."""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    blocks = BlockedUser.query.filter_by(user_id=current_user_id).all()
    blocked = []
    for block in blocks:
        user = User.query.get(block.blocked_user_id)
        if user:
            blocked.append(user_to_contact_dict(user))

    return jsonify({'success': True, 'blocked_users': blocked})
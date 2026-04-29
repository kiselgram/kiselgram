import json
import secrets
import os
from datetime import datetime
from flask import Blueprint, request, jsonify, session

from app import db
from app.models import User, Group, GroupMember, Message, BlockedUser
# If you add the GroupPermission model later, import it here:
# from app.models import GroupPermission
from app.utils.helpers import get_current_user_id, get_current_user, format_file_size

spa_groups_bp = Blueprint('spa_groups', __name__, url_prefix='/api')


def create_group_permissions(group_id):
    """Insert default permissions for a new group (if GroupPermission model exists)."""
    # This function should be implemented after adding the GroupPermission model.
    # For now we leave it empty – no permissions will be stored, but the
    # permission endpoints will still work with a stub.
    pass


def get_group_permissions(group_id, role):
    """Stub – returns default permissions if model not yet added."""
    # TODO: replace with actual database query once GroupPermission is available
    default_perms = {
        'can_send_messages': True,
        'can_send_media': True,
        'can_add_members': (role == 'owner' or role == 'admin'),
        'can_pin_messages': (role == 'owner' or role == 'admin'),
        'can_change_info': (role == 'owner' or role == 'admin'),
        'can_delete_messages': (role == 'owner' or role == 'admin'),
        'can_ban_users': (role == 'owner'),
    }
    return default_perms


def update_group_permissions_db(group_id, role, **kwargs):
    """Stub – update permissions in DB once model exists."""
    pass


# ==================== ENDPOINTS ====================

@spa_groups_bp.route('/groups/create', methods=['POST'])
def create_group():
    """
    Create a new group. Accepts JSON or multipart form data (with optional avatar).
    """
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    # Try to parse JSON or form data
    if request.is_json:
        data = request.get_json()
        name = data.get('name', '').strip()
        description = data.get('description', '')
        is_public = data.get('is_public', True)
        member_ids = data.get('member_ids', [])
    else:
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '')
        is_public = request.form.get('is_public', 'true').lower() == 'true'
        member_ids_str = request.form.get('member_ids', '[]')
        try:
            member_ids = json.loads(member_ids_str) if isinstance(member_ids_str, str) else member_ids_str
        except:
            member_ids = []

    if not name or len(name) < 3:
        return jsonify({'success': False, 'error': 'Group name must be at least 3 characters'}), 400

    invite_link = secrets.token_urlsafe(16)
    new_group = Group(
        name=name,
        description=description,
        owner_id=current_user_id,
        is_public=is_public,
        invite_link=invite_link,
        created_at=datetime.utcnow()
    )
    db.session.add(new_group)
    db.session.flush()

    # Handle avatar upload (if any)
    if 'avatar' in request.files:
        file = request.files['avatar']
        if file and file.filename:
            try:
                from PIL import Image
                ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
                filename = f"group_{new_group.id}_{secrets.token_urlsafe(8)}.{ext}"
                upload_dir = os.path.join('uploads', 'groups')
                os.makedirs(upload_dir, exist_ok=True)
                file_path = os.path.join(upload_dir, filename)
                img = Image.open(file)
                img.thumbnail((200, 200))
                img.save(file_path)
                new_group.avatar_url = f"/uploads/groups/{filename}"
            except:
                # If no PIL, just save the file as is
                ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
                filename = f"group_{new_group.id}_{secrets.token_urlsafe(8)}.{ext}"
                upload_dir = os.path.join('uploads', 'groups')
                os.makedirs(upload_dir, exist_ok=True)
                file_path = os.path.join(upload_dir, filename)
                file.save(file_path)
                new_group.avatar_url = f"/uploads/groups/{filename}"

    # Add creator as owner
    db.session.add(GroupMember(user_id=current_user_id, group_id=new_group.id, role='owner'))
    # Add initial members
    for member_id in member_ids:
        if member_id != current_user_id:
            db.session.add(GroupMember(user_id=member_id, group_id=new_group.id, role='member'))

    # Create default permissions (if model exists)
    create_group_permissions(new_group.id)

    db.session.commit()

    return jsonify({
        'success': True,
        'group': {
            'id': new_group.id,
            'name': new_group.name,
            'avatar_url': new_group.avatar_url,
            'invite_link': new_group.invite_link
        }
    })


@spa_groups_bp.route('/groups/<int:group_id>', methods=['GET'])
def get_group(group_id):
    """
    Get group details, members list, and current user's role/permissions.
    """
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    group = Group.query.get(group_id)
    if not group:
        return jsonify({'success': False, 'error': 'Group not found'}), 404

    # Check if user is a member (or if group is public)
    membership = GroupMember.query.filter_by(user_id=current_user_id, group_id=group_id).first()
    if not membership and not group.is_public:
        return jsonify({'success': False, 'error': 'You are not a member of this private group'}), 403

    # Build member list
    members = []
    for m in GroupMember.query.filter_by(group_id=group_id).all():
        user = User.query.get(m.user_id)
        if user:
            members.append({
                'id': user.id,
                'username': user.username,
                'display_name': user.display_name or user.username,
                'avatar_url': user.avatar_url,
                'role': m.role,
                'joined_at': m.joined_at.isoformat() if m.joined_at else None
            })

    user_role = membership.role if membership else None

    # Permissions for the current user's role
    permissions = get_group_permissions(group_id, user_role)

    return jsonify({
        'success': True,
        'group': {
            'id': group.id,
            'name': group.name,
            'description': group.description,
            'avatar_url': group.avatar_url,
            'is_public': group.is_public,
            'invite_link': group.invite_link,
            'owner_id': group.owner_id,
            'member_count': len(members),
        },
        'members': members,
        'user_role': user_role,
        'permissions': permissions
    })


@spa_groups_bp.route('/group_messages/<int:group_id>', methods=['GET'])
def get_group_messages(group_id):
    """
    Retrieve messages for a group chat. Supports ?after=<id> and limit.
    """
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    membership = GroupMember.query.filter_by(user_id=current_user_id, group_id=group_id).first()
    if not membership:
        return jsonify({'success': False, 'error': 'Not a member'}), 403

    after_id = request.args.get('after', 0, type=int)
    limit = request.args.get('limit', 50, type=int)

    messages = Message.query.filter_by(group_id=group_id) \
        .filter(Message.id > after_id) \
        .order_by(Message.timestamp.asc()) \
        .limit(limit).all()

    from app.routes.spa.chat import message_to_dict   # reuse converter from chat.py
    result = [message_to_dict(msg, current_user_id) for msg in messages]
    return jsonify({'success': True, 'messages': result})


@spa_groups_bp.route('/send_group_message', methods=['POST'])
def send_group_message():
    """
    Send a message to a group (including file attachments). Supports reply_to_id.
    """
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    # We accept both JSON and multipart (for file uploads)
    if request.is_json:
        data = request.get_json()
        group_id = data.get('group_id')
        content = data.get('content', '').strip()
        reply_to_id = data.get('reply_to_id')
        # No files in JSON – just text
        files = []
    else:
        group_id = request.form.get('group_id')
        content = request.form.get('content', '').strip()
        reply_to_id = request.form.get('reply_to_id')
        files = request.files.getlist('files')

    if not group_id:
        return jsonify({'success': False, 'error': 'group_id is required'}), 400
    group_id = int(group_id)

    # Verify membership
    membership = GroupMember.query.filter_by(user_id=current_user_id, group_id=group_id).first()
    if not membership:
        return jsonify({'success': False, 'error': 'Not a member'}), 403

    # Create the base message
    new_message = Message(
        sender_id=current_user_id,
        group_id=group_id,
        receiver_id=current_user_id,  # dummy
        content=content,
        timestamp=datetime.utcnow()
    )

    # Handle file uploads
    for file in files:
        if file and file.filename:
            file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
            file_type = get_file_type_from_ext(file_ext)
            unique_name = f"{secrets.token_urlsafe(16)}.{file_ext}"
            upload_dir = os.path.join('uploads', file_type + 's')  # images, videos, etc.
            os.makedirs(upload_dir, exist_ok=True)
            file_path = os.path.join(upload_dir, unique_name)
            file.save(file_path)
            file_size = os.path.getsize(file_path)
            new_message.has_attachment = True
            new_message.file_type = file_type
            new_message.file_path = os.path.relpath(file_path, 'uploads')
            new_message.file_name = file.filename
            new_message.file_size = file_size
            break  # only one file per message? For simplicity, use the first file.

    db.session.add(new_message)
    db.session.flush()

    # Handle reply
    if reply_to_id:
        original = Message.query.get(int(reply_to_id))
        if original:
            from app.models import Reply
            reply_rec = Reply(original_message_id=int(reply_to_id), reply_message_id=new_message.id)
            db.session.add(reply_rec)

    db.session.commit()

    from app.routes.spa.chat import message_to_dict
    return jsonify({'success': True, 'message': message_to_dict(new_message, current_user_id)})


@spa_groups_bp.route('/leave_group/<int:group_id>', methods=['POST'])
def leave_group(group_id):
    """Leave a group. Owners leaving deletes the group if no other owner."""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    membership = GroupMember.query.filter_by(user_id=current_user_id, group_id=group_id).first()
    if not membership:
        return jsonify({'success': False, 'error': 'Not a member'}), 400

    if membership.role == 'owner':
        # Transfer ownership to another admin, or delete the group
        other_admin = GroupMember.query.filter(GroupMember.group_id == group_id,
                                               GroupMember.user_id != current_user_id,
                                               GroupMember.role == 'admin').first()
        if other_admin:
            other_admin.role = 'owner'
            db.session.delete(membership)
        else:
            # No admin – delete the group
            Group.query.filter_by(id=group_id).delete()
            # Cascade will delete members and messages
    else:
        db.session.delete(membership)

    db.session.commit()
    return jsonify({'success': True, 'message': 'You have left the group'})


@spa_groups_bp.route('/join_group/<invite_link>', methods=['GET'])
def join_group(invite_link):
    """Join a public group via its invite link."""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    group = Group.query.filter_by(invite_link=invite_link).first()
    if not group:
        return jsonify({'success': False, 'error': 'Group not found'}), 404

    existing = GroupMember.query.filter_by(user_id=current_user_id, group_id=group.id).first()
    if existing:
        return jsonify({'success': True, 'already_member': True, 'group_id': group.id})

    db.session.add(GroupMember(user_id=current_user_id, group_id=group.id, role='member'))
    db.session.commit()
    return jsonify({'success': True, 'group_id': group.id})


# ==================== GROUP MANAGEMENT (owner/admin) ====================

@spa_groups_bp.route('/groups/<int:group_id>/update', methods=['POST'])
def update_group(group_id):
    """Update group name, description, or public/private setting. Owner or admin only."""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    membership = GroupMember.query.filter_by(user_id=current_user_id, group_id=group_id).first()
    if not membership or membership.role not in ('owner', 'admin'):
        return jsonify({'success': False, 'error': 'Insufficient permissions'}), 403

    group = Group.query.get(group_id)
    if not group:
        return jsonify({'success': False, 'error': 'Group not found'}), 404

    data = request.get_json() or {}
    if 'name' in data:
        group.name = data['name']
    if 'description' in data:
        group.description = data['description']
    if 'is_public' in data:
        group.is_public = data['is_public']

    db.session.commit()
    return jsonify({'success': True})


@spa_groups_bp.route('/groups/<int:group_id>/members/<int:user_id>/role', methods=['POST'])
def update_member_role(group_id, user_id):
    """Change a member's role (owner/admin can promote/demote). Cannot demote owner."""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    membership = GroupMember.query.filter_by(user_id=current_user_id, group_id=group_id).first()
    if not membership or membership.role not in ('owner', 'admin'):
        return jsonify({'success': False, 'error': 'Insufficient permissions'}), 403

    target_membership = GroupMember.query.filter_by(user_id=user_id, group_id=group_id).first()
    if not target_membership:
        return jsonify({'success': False, 'error': 'Member not found'}), 404

    if target_membership.role == 'owner':
        return jsonify({'success': False, 'error': 'Cannot change the owner'}), 400

    data = request.get_json() or {}
    new_role = data.get('role')
    if new_role not in ('member', 'admin'):
        return jsonify({'success': False, 'error': 'Invalid role'}), 400

    target_membership.role = new_role
    db.session.commit()
    return jsonify({'success': True})


@spa_groups_bp.route('/groups/<int:group_id>/members/<int:user_id>', methods=['DELETE'])
def remove_member(group_id, user_id):
    """Remove a member from the group. Owner/admin can remove non‑owners."""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    membership = GroupMember.query.filter_by(user_id=current_user_id, group_id=group_id).first()
    if not membership or membership.role not in ('owner', 'admin'):
        return jsonify({'success': False, 'error': 'Insufficient permissions'}), 403

    target = GroupMember.query.filter_by(user_id=user_id, group_id=group_id).first()
    if not target:
        return jsonify({'success': False, 'error': 'Member not found'}), 404

    if target.role == 'owner':
        return jsonify({'success': False, 'error': 'Cannot remove the owner'}), 400

    db.session.delete(target)
    db.session.commit()
    return jsonify({'success': True})


# ==================== GROUP PERMISSIONS ====================

@spa_groups_bp.route('/groups/<int:group_id>/permissions', methods=['GET'])
def get_permissions(group_id):
    """Get all role‑based permissions for a group."""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    membership = GroupMember.query.filter_by(user_id=current_user_id, group_id=group_id).first()
    if not membership or membership.role != 'owner':
        return jsonify({'success': False, 'error': 'Only the owner can view permissions'}), 403

    # Return permissions for all roles (stub)
    roles = ['owner', 'admin', 'member']
    perms = {}
    for role in roles:
        perms[role] = get_group_permissions(group_id, role)

    return jsonify({'success': True, 'permissions': perms})


@spa_groups_bp.route('/groups/<int:group_id>/permissions', methods=['POST'])
def update_permissions(group_id):
    """Update permissions for a specific role."""
    current_user_id = get_current_user_id()
    if not current_user_id:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    membership = GroupMember.query.filter_by(user_id=current_user_id, group_id=group_id).first()
    if not membership or membership.role != 'owner':
        return jsonify({'success': False, 'error': 'Only the owner can change permissions'}), 403

    data = request.get_json() or {}
    role = data.get('role')
    permissions = data.get('permissions', {})

    if role not in ('admin', 'member'):
        return jsonify({'success': False, 'error': 'Invalid role'}), 400

    update_group_permissions_db(group_id, role, **permissions)
    return jsonify({'success': True})


# ==================== HELPER ====================

def get_file_type_from_ext(ext):
    if ext in ('jpg', 'jpeg', 'png', 'gif', 'webp'):
        return 'image'
    elif ext in ('mp4', 'avi', 'mov', 'mkv'):
        return 'video'
    elif ext in ('mp3', 'wav', 'ogg', 'm4a'):
        return 'audio'
    else:
        return 'document'
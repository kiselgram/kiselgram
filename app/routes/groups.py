from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from app import db
from app.models import Group, GroupMember, Message
from app.utils.helpers import get_current_user, get_current_user_id, generate_invite_link

groups_bp = Blueprint('groups', __name__)

@groups_bp.route('/create_group', methods=['GET', 'POST'])
def create_group():
    if not get_current_user():
        return redirect('/')

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        is_public = request.form.get('is_public') == 'on'

        if not name:
            return render_template('create_group.html', error="Group name is required")

        try:
            invite_link = generate_invite_link()
            new_group = Group(
                name=name,
                description=description,
                owner_id=get_current_user_id(),
                is_public=is_public,
                invite_link=invite_link
            )
            db.session.add(new_group)
            db.session.flush()

            # Add creator as owner
            membership = GroupMember(
                user_id=get_current_user_id(),
                group_id=new_group.id,
                role='owner'
            )
            db.session.add(membership)
            db.session.commit()

            return redirect(f'/group/{new_group.id}')
        except Exception as e:
            db.session.rollback()
            return render_template('create_group.html', error="Error creating group")

    return render_template('create_group.html')

@groups_bp.route('/group/<int:group_id>')
def group_chat(group_id):
    if not get_current_user():
        return redirect('/')

    group = Group.query.get_or_404(group_id)
    membership = GroupMember.query.filter_by(user_id=get_current_user_id(), group_id=group_id).first()
    if not membership:
        return redirect('/join_group/' + group.invite_link)

    return render_template('group.html', current_user=get_current_user(), group=group)

@groups_bp.route('/join_group/<invite_link>')
def join_group(invite_link):
    if not get_current_user():
        return redirect('/')

    group = Group.query.filter_by(invite_link=invite_link).first_or_404()

    existing_member = GroupMember.query.filter_by(user_id=get_current_user_id(), group_id=group.id).first()
    if existing_member:
        return redirect(f'/group/{group.id}')

    try:
        membership = GroupMember(
            user_id=get_current_user_id(),
            group_id=group.id,
            role='member'
        )
        db.session.add(membership)
        db.session.commit()
        return redirect(f'/group/{group.id}')
    except:
        db.session.rollback()
        return redirect('/chat_list')

@groups_bp.route('/group_info/<int:group_id>')
def group_info(group_id):
    if not get_current_user():
        return redirect('/')

    group = Group.query.get_or_404(group_id)
    membership = GroupMember.query.filter_by(user_id=get_current_user_id(), group_id=group_id).first()
    if not membership:
        return redirect('/join_group/' + group.invite_link)

    members = GroupMember.query.filter_by(group_id=group_id).all()
    return render_template('group_info.html', current_user=get_current_user(), group=group, members=members)

@groups_bp.route('/leave_group/<int:group_id>')
def leave_group(group_id):
    if not get_current_user():
        return redirect('/')

    membership = GroupMember.query.filter_by(user_id=get_current_user_id(), group_id=group_id).first()
    if membership:
        if membership.role == 'owner':
            Message.query.filter_by(group_id=group_id).delete()
            GroupMember.query.filter_by(group_id=group_id).delete()
            Group.query.filter_by(id=group_id).delete()
        else:
            db.session.delete(membership)

        db.session.commit()

    return redirect('/chat_list')


# Add to routes/groups.py

@groups_bp.route('/group_members/<int:group_id>')
def group_members(group_id):
    """View group members"""
    if not get_current_user():
        return redirect('/')

    group = Group.query.get_or_404(group_id)
    current_user_id = get_current_user_id()

    # Check if user is member
    membership = GroupMember.query.filter_by(user_id=current_user_id, group_id=group_id).first()
    if not membership:
        return redirect('/chat_list')

    members = []
    for gm in group.members:
        members.append({
            'id': gm.user.id,
            'username': gm.user.username,
            'role': gm.role,
            'joined_at': gm.joined_at
        })

    return render_template('group_members.html',
                           group=group,
                           members=members,
                           current_user=get_current_user(),
                           is_admin=membership.role == 'admin')
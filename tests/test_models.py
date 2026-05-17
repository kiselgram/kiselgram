# tests/test_models.py
import pytest
from app.models import User, Message, Group, Channel, GroupMember
from datetime import datetime
from app import db

def test_new_user(session):
    user = User(username="alice", email="alice@test.com")
    user.set_password("secret")
    session.add(user)
    session.commit()
    assert user.id is not None
    assert user.check_password("secret")
    assert not user.check_password("wrong")
    assert user.email_verified == False
    assert user.is_online == False
    assert user.last_seen is not None

def test_user_unique_constraints(session):
    user1 = User(username="bob", email="bob@test.com")
    user1.set_password("123")
    session.add(user1)
    session.commit()

    # duplicate username
    user2 = User(username="bob", email="bob2@test.com")
    session.add(user2)
    with pytest.raises(Exception):
        session.commit()
    session.rollback()

    # duplicate email
    user3 = User(username="bob2", email="bob@test.com")
    session.add(user3)
    with pytest.raises(Exception):
        session.commit()

def test_message_send(session, user, user2):
    msg = Message(
        content="Hello",
        sender=user,
        receiver=user2,
        timestamp=datetime.utcnow()
    )
    session.add(msg)
    session.commit()
    assert msg.id is not None
    assert msg.is_read == False
    assert msg.has_attachment == False
    assert msg.is_deleted == False

def test_group_creation(session, user):
    group = Group(name="Test Group", owner_id=user.id)
    session.add(group)
    session.commit()
    gm = GroupMember(user=user, group=group, role="owner")
    session.add(gm)
    session.commit()
    assert group.members[0].user == user
    assert group.members[0].role == "owner"
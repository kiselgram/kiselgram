# tests/test_auth.py
from app import db
from app.models import User, EmailVerification

def test_register_user(client, session):
    response = client.post("/auth/register", data={
        "username": "newuser",
        "email": "new@test.com",
        "password": "strongpass",          # 10 chars -> OK
        "confirm_password": "strongpass"
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"verify" in response.data.lower() or b"check" in response.data.lower()

    user = User.query.filter_by(username="newuser").first()
    assert user is not None
    assert user.email_verified == False
    assert user.check_password("strongpass")
    ver = EmailVerification.query.filter_by(user_id=user.id).first()
    assert ver is not None

def test_register_password_mismatch(client, session):
    response = client.post("/auth/register", data={
        "username": "fail",
        "email": "fail@test.com",
        "password": "a",
        "confirm_password": "b"
    })
    assert b"do not match" in response.data.lower()

def test_login_logout(client, user):
    resp = client.post("/auth/login", data={
        "username": user.username,
        "password": "testpass"             # user fixture uses 'testpass' (8 chars)
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "chat_list" in resp.request.url

    with client.session_transaction() as sess:
        assert sess.get("user_id") == user.id

    resp = client.get("/logout", follow_redirects=True)
    with client.session_transaction() as sess:
        assert "user_id" not in sess

def test_email_verification_flow(client, session):
    # Use a password that meets the minimum length (6 characters)
    client.post("/auth/register", data={
        "username": "verifyuser",
        "email": "verify@test.com",
        "password": "validpass",           # 9 chars
        "confirm_password": "validpass"
    })
    user = User.query.filter_by(username="verifyuser").first()
    assert user is not None, "User was not created – check password length requirement (≥ 6)"
    ver = EmailVerification.query.filter_by(user_id=user.id).first()
    token = ver.token

    resp = client.get(f"/auth/verify/{token}", follow_redirects=True)
    assert resp.status_code == 200
    with client.session_transaction() as sess:
        assert sess.get("user_id") == user.id

    user = User.query.get(user.id)
    assert user.email_verified == True

def test_complete_registration(client, user):
    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["username"] = user.username

    resp = client.post("/auth/complete-registration", data={
        "username": "testuser_final",
        "display_name": "Test User Final",
        "avatar": "avatar1.jpg"
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert "chat_list" in resp.request.url

    updated = User.query.get(user.id)
    assert updated.username == "testuser_final"
    assert updated.display_name == "Test User Final"
    assert updated.avatar_url == "avatar1.jpg"
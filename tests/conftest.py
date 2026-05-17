# tests/conftest.py
import pytest
from app import create_app, db as _db
from app.models import User
from datetime import datetime

TEST_DB = "sqlite:///test.db"

@pytest.fixture(scope="session")
def app():
    """Create the Flask app with all blueprints registered."""
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = TEST_DB
    app.config["MAIL_SUPPRESS_SEND"] = True

    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()

@pytest.fixture(scope="function")
def client(app):
    return app.test_client()

@pytest.fixture(scope="function")
def session(app):
    with app.app_context():
        _db.session.remove()
        _db.drop_all()
        _db.create_all()
        yield _db.session
        _db.session.rollback()

@pytest.fixture
def user(session):
    u = User(
        username="testuser",
        email="test@example.com",
        email_verified=True,
        display_name="Test User",
    )
    u.set_password("testpass")
    session.add(u)
    session.commit()
    return u

@pytest.fixture
def user2(session):
    u = User(
        username="friend",
        email="friend@example.com",
        email_verified=True,
        display_name="Friend",
    )
    u.set_password("friendpass")
    session.add(u)
    session.commit()
    return u

@pytest.fixture
def logged_in_client(client, user):
    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["username"] = user.username
    return client
# tests/test_api_spa.py
import json
from datetime import datetime
from app.models import Message
from app import db

def test_get_chat_list_authenticated(logged_in_client, user):
    resp = logged_in_client.get("/api/chat_list")
    assert resp.status_code == 200
    assert resp.is_json
    data = resp.get_json()
    assert data["success"] == True
    assert "chats" in data

def test_send_and_receive_message(logged_in_client, user, user2):
    payload = {"receiver_id": user2.id, "content": "Hello from test"}
    resp = logged_in_client.post("/api/send_message", json=payload)
    assert resp.status_code == 200
    assert resp.is_json, f"Expected JSON, got {resp.data[:200]}"
    data = resp.get_json()
    assert data["success"] == True
    message = data["message"]
    assert message["content"] == "Hello from test"
    assert message["sender_id"] == user.id

    # Login as user2
    client2 = logged_in_client.application.test_client()
    with client2.session_transaction() as sess:
        sess["user_id"] = user2.id
        sess["username"] = user2.username

    resp2 = client2.get(f"/api/messages/{user.id}")
    assert resp2.status_code == 200
    assert resp2.is_json
    messages = resp2.get_json()["messages"]
    assert len(messages) == 1
    assert messages[0]["content"] == "Hello from test"

def test_mark_read(logged_in_client, user, user2):
    # Create a message from user2 to user
    msg = Message(content="unread", sender_id=user2.id, receiver_id=user.id,
                  timestamp=datetime.utcnow())
    db.session.add(msg)
    db.session.commit()

    resp = logged_in_client.post(f"/api/mark_read/{user2.id}")
    assert resp.status_code == 200
    assert resp.get_json()["success"] == True

    updated = Message.query.get(msg.id)
    assert updated.is_read == True

def test_reactions(logged_in_client, user, user2):
    # Send a message first
    resp = logged_in_client.post("/api/send_message",
                                 json={"receiver_id": user2.id, "content": "react test"})
    assert resp.status_code == 200
    assert resp.is_json
    msg_id = resp.get_json()["message"]["id"]

    # Add reaction
    resp = logged_in_client.post("/api/reactions/add",
                                 json={"message_id": msg_id, "reaction_type": "❤️"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"]
    reactions = data["reactions"]
    assert any(r["type"] == "❤️" and r["count"] == 1 for r in reactions)

def test_privacy_settings(logged_in_client, user):
    # GET current settings
    resp = logged_in_client.get("/api/profile/privacy")
    assert resp.status_code == 200
    assert resp.is_json
    data = resp.get_json()
    assert data["success"]

    # Update – now uses the correct keys matching the fixed server
    resp = logged_in_client.put("/api/profile/privacy", json={
        "last_seen": "contacts",
        "profile_photo": "nobody",
        "calls": "contacts",
        "messages": "contacts"
    })
    assert resp.status_code == 200
    assert resp.get_json()["success"] == True

    # Verify
    resp = logged_in_client.get("/api/profile/privacy")
    settings = resp.get_json()["privacy"]
    assert settings["last_seen"] == "contacts"

def test_sessions(logged_in_client):
    resp = logged_in_client.get("/api/sessions")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"]
    assert isinstance(data["sessions"], list)
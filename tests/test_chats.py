# tests/test_chats.py
def test_chat_list_page_requires_login(client):
    resp = client.get("/chat_list", follow_redirects=True)
    assert b"login" in resp.data.lower()

def test_chat_list_page_renders(logged_in_client):
    resp = logged_in_client.get("/chat_list")
    assert resp.status_code == 200
    assert b"Kiselgram" in resp.data
    # Check for saved messages item
    assert b"Saved Messages" in resp.data

def test_about_page(client):
    resp = client.get("/kis_info")
    assert resp.status_code == 200
    assert b"v4.0.0" in resp.data

def test_premium_page_requires_login(client):
    resp = client.get("/premium", follow_redirects=True)
    assert b"login" in resp.data.lower()
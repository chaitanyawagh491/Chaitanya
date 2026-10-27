import os
import sqlite3
import pytest
from pathlib import Path
from server.db import init_db, get_db_connection, hash_password
from server.app import app, init_local_db

@pytest.fixture
def test_client(tmp_path, monkeypatch):
    test_db = tmp_path / "test_auth.db"
    monkeypatch.setattr("server.db.DB_PATH", test_db)
    monkeypatch.setattr("server.app.DB_PATH", test_db)
    
    init_local_db()
    
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_admin_seeding_in_db(test_client, tmp_path):
    test_db = tmp_path / "test_auth.db"
    conn = sqlite3.connect(str(test_db))
    cursor = conn.cursor()
    cursor.execute("SELECT username, role, credits_unlimited FROM users WHERE username = 'admin'")
    row = cursor.fetchone()
    conn.close()
    
    assert row is not None
    assert row[0] == "admin"
    assert row[1] == "admin"
    assert row[2] == 1

def test_server_ping_endpoint(test_client):
    response = test_client.get("/api/ping")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "online"
    assert data["database"] == "connected"

def test_server_admin_login(test_client):
    response = test_client.post("/api/login", json={
        "username": "admin",
        "password": "admin123",
        "hwid": "test_hwid_12345"
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["user_data"]["role"] == "admin"
    assert "token" in data

def test_server_user_registration_and_login(test_client, tmp_path):
    test_db = tmp_path / "test_auth.db"
    conn = sqlite3.connect(str(test_db))
    cursor = conn.cursor()
    cursor.execute("INSERT INTO invite_keys (key) VALUES ('INVITE-TEST-KEY-123')")
    conn.commit()
    conn.close()
    
    # Register new user with invite key
    reg_resp = test_client.post("/api/register", json={
        "username": "testuser",
        "password": "testpassword123",
        "hwid": "test_hwid_9999",
        "invite_key": "INVITE-TEST-KEY-123"
    })
    assert reg_resp.status_code == 201
    reg_data = reg_resp.get_json()
    assert reg_data["success"] is True
    
    # Login with new user
    login_resp = test_client.post("/api/login", json={
        "username": "testuser",
        "password": "testpassword123",
        "hwid": "test_hwid_9999"
    })
    assert login_resp.status_code == 200
    login_data = login_resp.get_json()
    assert login_data["success"] is True
    assert login_data["user_data"]["role"] == "user"
    assert login_data["user_data"]["credits"] == 15

def test_server_local_session(test_client):
    response = test_client.post("/api/local-session", json={
        "hwid": "test_hwid_local_123"
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["user_data"]["username"] == "local_user"
    assert data["user_data"]["role"] == "user"
    assert "token" in data


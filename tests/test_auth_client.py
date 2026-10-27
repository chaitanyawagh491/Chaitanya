import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from network.auth_client import AuthClient

def test_machine_hwid_generation(tmp_path):
    client = AuthClient("TestApp", "TestOwner", "3.0.0", tmp_path)
    hwid = client.hwid
    assert isinstance(hwid, str)
    assert len(hwid) > 0
    # Consistent resolution
    hwid2 = client._get_local_hwid()
    assert hwid == hwid2

def test_cached_credentials_cipher_roundtrip(tmp_path):
    client = AuthClient("TestApp", "TestOwner", "3.0.0", tmp_path)
    test_plaintext = "username:secure_password_test_123"
    
    encrypted = client._xor_cipher(test_plaintext)
    assert encrypted != test_plaintext
    
    decrypted = client._xor_cipher(encrypted)
    assert decrypted == test_plaintext

def test_save_and_load_cached_credentials(tmp_path):
    client = AuthClient("TestApp", "TestOwner", "3.0.0", tmp_path)
    client.save_credentials("userpass", "test_user", "test_pass")
    
    cached = client.load_cached_credentials()
    assert cached is not None
    assert cached["type"] == "userpass"
    assert cached["key_or_user"] == "test_user"
    assert cached["password"] == "test_pass"

def test_auth_client_initialize(tmp_path):
    client = AuthClient("TestApp", "TestOwner", "3.0.0", tmp_path)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "online", "database": "connected"}
    
    with patch.object(client, "_execute_request", return_value=mock_resp):
        res = client.initialize()
        assert res is True

def test_auth_client_get_or_create_local_session_online(tmp_path):
    client = AuthClient("TestApp", "TestOwner", "3.0.0", tmp_path)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "success": True,
        "token": "test_jwt_token",
        "user_data": {"username": "local_user", "credits": 9999}
    }
    
    with patch.object(client, "_execute_request", return_value=mock_resp):
        res = client.get_or_create_local_session()
        assert res["success"] is True
        assert res["token"] == "test_jwt_token"
        assert client.session_token == "test_jwt_token"
        assert client.user_info["username"] == "local_user"

def test_auth_client_get_or_create_local_session_offline_fallback(tmp_path):
    client = AuthClient("TestApp", "TestOwner", "3.0.0", tmp_path)
    
    with patch.object(client, "_execute_request", side_effect=Exception("Connection refused")):
        res = client.get_or_create_local_session()
        assert res["success"] is True
        assert res["token"] == "local_standalone_token"
        assert client.session_token == "local_standalone_token"
        assert client.user_info["username"] == "Local User"
        assert client.user_info["credits_unlimited"] is True


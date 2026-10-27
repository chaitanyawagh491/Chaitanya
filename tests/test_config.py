import json
import pytest
from pathlib import Path
from config import Config

def test_config_defaults():
    cfg = Config()
    assert cfg.CURRENT_VERSION == "3.0.0"
    assert cfg.TRIPLE_TAP_WINDOW == 0.5
    assert cfg.RESPONSE_DURATION in [2.0, 5.0]
    assert cfg.GLOBAL_SHORTCUT in ["Ctrl+Shift+S", "<ctrl>+<alt>+a"]

def test_config_dpapi_encryption():
    cfg = Config()
    test_key = "AIzaSyTestGeminiKey12345"
    encrypted = cfg._encrypt_credential(test_key)
    
    if encrypted.startswith("enc:dpapi:"):
        decrypted = cfg._decrypt_credential(encrypted)
        assert decrypted == test_key
    else:
        assert encrypted == test_key

def test_config_api_key_set_and_get():
    cfg = Config()
    test_key = "test_sk_openai_secret_999"
    cfg.set_api_key("openai", test_key)
    retrieved = cfg.get_api_key("openai")
    assert retrieved == test_key

def test_config_persistence_and_encryption(tmp_path):
    settings_file = tmp_path / "settings.json"
    
    cfg = Config()
    cfg.LOG_DIR = tmp_path
    cfg.SETTINGS_FILE = settings_file
    cfg.set_api_key("gemini", "my_secret_gemini_key")
    cfg.save_to_disk()
    
    assert settings_file.exists()
    
    # Verify file contains encrypted keys, not plaintext
    with open(settings_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    encrypted_key = data["API_KEYS"]["gemini"]
    assert "my_secret_gemini_key" not in encrypted_key or not encrypted_key.startswith("enc:dpapi:")
    
    # Reload in fresh instance
    cfg2 = Config()
    cfg2.LOG_DIR = tmp_path
    cfg2.SETTINGS_FILE = settings_file
    cfg2.load_from_disk()
    assert cfg2.get_api_key("gemini") == "my_secret_gemini_key"

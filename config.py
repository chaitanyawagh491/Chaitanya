import os
import sys
import json
import base64
import logging
from pathlib import Path
from dotenv import load_dotenv
from dataclasses import dataclass, field

load_dotenv()

logger = logging.getLogger("Config")

@dataclass
class Config:
    CURRENT_VERSION: str = "3.0.0"
    AUTH_SERVER_URL: str = os.getenv("AUTH_SERVER_URL", "http://127.0.0.1:5000")
    
    # Active visual provider and model settings
    ACTIVE_PROVIDER: str = "gemini"
    ACTIVE_MODEL: str = "gemini-3.5-flash-lite"
    
    # Provider keys
    API_KEYS: dict = field(default_factory=lambda: {
        "gemini": os.getenv("GEMINI_API_KEY", ""),
        "openrouter": os.getenv("OPENROUTER_API_KEY", ""),
        "openai": os.getenv("OPENAI_API_KEY", "")
    })
    
    # Fallback configuration
    FALLBACK_ENABLED: bool = True
    FALLBACK_PROVIDER: str = "openrouter"
    FALLBACK_MODEL: str = "google/gemini-2.5-flash"
    
    TRIPLE_TAP_WINDOW: float = float(os.getenv("TRIPLE_TAP_WINDOW", "0.5"))
    TAP_DETECTION_RADIUS: int = 50
    CROP_BOX: list = None
    RESPONSE_DURATION: float = float(os.getenv("RESPONSE_DURATION", "3.0"))
    RESPONSE_FONT_SIZE: int = 13
    RESPONSE_TEXT_COLOR: list = field(default_factory=lambda: [255, 255, 255])
    RESPONSE_BG_COLOR: list = field(default_factory=lambda: [0, 0, 0])
    RESPONSE_OPACITY: float = 0.95
    INJECT_X: int = 30
    INJECT_Y: int = 30
    INJECT_WIDTH: int = 1200

    INJECT_MAX_HEIGHT: int = 400
    MAX_RESPONSE_LENGTH: int = 300
    API_TIMEOUT: int = 20
    GLOBAL_SHORTCUT: str = os.getenv("GLOBAL_SHORTCUT", "Ctrl+Shift+S")
    HIDE_PROCESS: bool = os.getenv("HIDE_PROCESS", "true").lower() == "true"
    HIDE_CONSOLE: bool = os.getenv("HIDE_CONSOLE", "true").lower() == "true"
    HIDE_WINDOW: bool = True
    HIDE_FROM_TASKBAR: bool = True
    DISABLE_CAPTURE_PROTECTION: bool = os.getenv("DISABLE_CAPTURE_PROTECTION", "false").lower() == "true"
    LOG_DIR: Path = Path.home() / ".core_portal"
    LOG_FILE: Path = Path.home() / ".core_portal" / "portal.log"
    CRASH_LOG_FILE: Path = Path.home() / ".core_portal" / "crash.log"
    TEST_LOG_FILE: Path = Path.home() / ".core_portal" / "test.log"
    SETTINGS_FILE: Path = Path.home() / ".core_portal" / "settings.json"
    DEBUG_MODE: bool = os.getenv("DEBUG_MODE", "false").lower() == "true"
    SAFE_MODE: bool = False

    def __post_init__(self):
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.load_from_disk()

    @staticmethod
    def _encrypt_credential(val: str) -> str:
        if not val or not isinstance(val, str):
            return ""
        if sys.platform == "win32":
            try:
                import win32crypt
                enc = win32crypt.CryptProtectData(val.encode("utf-8"), "portal_key", None, None, None, 0)
                return "enc:dpapi:" + base64.b64encode(enc).decode("ascii")
            except Exception as e:
                logger.debug(f"DPAPI encryption fallback: {e}")
        return val

    @staticmethod
    def _decrypt_credential(val: str) -> str:
        if not val or not isinstance(val, str):
            return ""
        if val.startswith("enc:dpapi:"):
            if sys.platform == "win32":
                try:
                    import win32crypt
                    raw = base64.b64decode(val[len("enc:dpapi:"):])
                    dec = win32crypt.CryptUnprotectData(raw, None, None, None, 0)[1]
                    return dec.decode("utf-8")
                except Exception as e:
                    logger.error(f"Failed to decrypt credential: {e}")
                    return ""
            return ""
        return val

    def load_from_disk(self):
        if not self.SETTINGS_FILE.exists():
            return
        try:
            with open(self.SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved_data = json.load(f)
            allowed_fields = [
                "TRIPLE_TAP_WINDOW",
                "CROP_BOX",
                "RESPONSE_DURATION",
                "DEBUG_MODE",
                "GLOBAL_SHORTCUT",
                "ACTIVE_PROVIDER",
                "ACTIVE_MODEL",
                "FALLBACK_ENABLED",
                "FALLBACK_PROVIDER",
                "FALLBACK_MODEL",
            ]
            for field_name in allowed_fields:
                if field_name in saved_data and hasattr(self, field_name):
                    setattr(self, field_name, saved_data[field_name])
            if "API_KEYS" in saved_data and isinstance(saved_data["API_KEYS"], dict):
                for k, v in saved_data["API_KEYS"].items():
                    if isinstance(v, str):
                        self.API_KEYS[k.lower()] = self._decrypt_credential(v)
            
            # Smoothly migrate obsolete/exhausted Gemini models to supported flash-lite model
            if self.ACTIVE_PROVIDER == "gemini" and self.ACTIVE_MODEL in [
                "gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.0-pro", "gemini-3.5-flash"
            ]:
                logger.info(f"Auto-migrating Gemini model '{self.ACTIVE_MODEL}' to 'gemini-3.5-flash-lite'.")
                self.ACTIVE_MODEL = "gemini-3.5-flash-lite"
                self.save_to_disk()

            logger.info("Configuration preferences loaded from settings.json.")
        except Exception as e:
            logger.error(f"Failed to load settings.json: {e}")


    def save_to_disk(self):
        try:
            self.LOG_DIR.mkdir(parents=True, exist_ok=True)
            encrypted_keys = {}
            for k, v in self.API_KEYS.items():
                encrypted_keys[k.lower()] = self._encrypt_credential(v)
            serializable = {
                "TRIPLE_TAP_WINDOW": self.TRIPLE_TAP_WINDOW,
                "CROP_BOX": self.CROP_BOX,
                "RESPONSE_DURATION": self.RESPONSE_DURATION,
                "DEBUG_MODE": self.DEBUG_MODE,
                "GLOBAL_SHORTCUT": self.GLOBAL_SHORTCUT,
                "ACTIVE_PROVIDER": self.ACTIVE_PROVIDER,
                "ACTIVE_MODEL": self.ACTIVE_MODEL,
                "API_KEYS": encrypted_keys,
                "FALLBACK_ENABLED": self.FALLBACK_ENABLED,
                "FALLBACK_PROVIDER": self.FALLBACK_PROVIDER,
                "FALLBACK_MODEL": self.FALLBACK_MODEL,
            }
            with open(self.SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(serializable, f, indent=4)
            logger.info("Configuration saved to settings.json.")
        except Exception as e:
            logger.error(f"Failed to save settings.json: {e}")

    def get_api_key(self, provider: str) -> str:
        return self.API_KEYS.get(provider.lower(), "")

    def set_api_key(self, provider: str, key: str) -> None:
        self.API_KEYS[provider.lower()] = key

    def has_primary_key(self) -> bool:
        return bool(self.get_api_key(self.ACTIVE_PROVIDER))

    def has_fallback_key(self) -> bool:
        if self.FALLBACK_ENABLED:
            return bool(self.get_api_key(self.FALLBACK_PROVIDER))
        return False

    def validate(self) -> bool:
        if not self.has_primary_key():
            raise ValueError(
                f"No API key configured for the active visual analysis provider '{self.ACTIVE_PROVIDER}'. "
                "Configure it in settings."
            )
        return True

config = Config()
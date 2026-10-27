import logging
import hashlib
import sys
import os
import json
import platform
import subprocess
import requests
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger("AuthClient")

class AuthClient:
    def __init__(self, name: str, owner_id: str, version: str, data_dir: Path):
        self.version = version
        self.data_dir = data_dir
        self.credentials_file = data_dir / "auth.cache"
        self.is_demo = False
        from config import config
        self.server_url = config.AUTH_SERVER_URL.rstrip('/')
        self.user_info = {}
        self.session_token = ""
        self.hwid = self._get_local_hwid()
        logger.info(f"Hardware fingerprint resolved.")

    def _get_local_hwid(self) -> str:
        system_platform = platform.system()
        if system_platform == "Linux":
            try:
                with open("/etc/machine-id") as f:
                    return f.read().strip()
            except Exception:
                pass
        elif system_platform == 'Windows':
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                    guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                    if guid:
                        return str(guid).strip()
            except Exception:
                pass
            try:
                import win32security
                winuser = os.getlogin()
                sid, _, _ = win32security.LookupAccountName(None, winuser)
                hwid = win32security.ConvertSidToStringSid(sid)
                if hwid:
                    return hwid
            except Exception:
                pass
            try:
                cmd = subprocess.Popen(
                    ["wmic", "csproduct", "get", "uuid"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=0x08000000
                )
                stdout, _ = cmd.communicate()
                uuid_lines = stdout.split(b"\n")
                if len(uuid_lines) > 1:
                    uuid_str = uuid_lines[1].strip().decode()
                    if uuid_str:
                        return uuid_str
            except Exception:
                pass
        elif system_platform == 'Darwin':
            try:
                output = subprocess.Popen("ioreg -l | grep IOPlatformSerialNumber", stdout=subprocess.PIPE, shell=True).communicate()[0]
                serial = output.decode().split('=', 1)[1].replace(' ', '')
                return serial[1:-2]
            except Exception:
                pass
        import uuid
        return hashlib.sha256(str(uuid.getnode()).encode()).hexdigest()

    def _execute_request(self, method: str, url: str, **kwargs) -> requests.Response:
        try:
            res = requests.request(method, url, **kwargs)
            return res
        except requests.exceptions.Timeout:
            raise RuntimeError("Request timed out. Please try again.")
        except requests.exceptions.ConnectionError:
            raise RuntimeError("Unable to connect to the server. Please check your internet connection.")
        except requests.exceptions.RequestException:
            raise RuntimeError("A network error occurred.")

    def initialize(self) -> bool:
        try:
            res = self._execute_request("GET", f"{self.server_url}/api/ping", timeout=8)
            if res.status_code == 200:
                return True
            return False
        except Exception:
            return False

    def check_connectivity(self) -> Dict[str, str]:
        status = {
            "internet": "red",
            "server": "red",
            "database": "red",
            "visual_system": "red",
            "config": "green",
            "update": "red",
            "storage": "red"
        }
        try:
            res = requests.get("https://1.1.1.1", timeout=3)
            if res.status_code == 200:
                status["internet"] = "green"
        except Exception:
            status["internet"] = "red"
        if status["internet"] == "green":
            try:
                res = requests.get(f"{self.server_url}/api/ping", timeout=4)
                if res.status_code == 200:
                    status["server"] = "green"
                    data = res.json()
                    if data.get("database") == "connected":
                        status["database"] = "green"
            except Exception:
                pass
        try:
            from PIL import ImageGrab
            screenshot = ImageGrab.grab(bbox=(0, 0, 1, 1))
            if screenshot and screenshot.size[0] > 0:
                status["visual_system"] = "green"
            else:
                status["visual_system"] = "yellow"
        except Exception:
            pass
        if status["internet"] == "green" and status["server"] == "green":
            try:
                res = requests.get(f"{self.server_url}/api/update?version={self.version}", timeout=4)
                if res.status_code == 200:
                    status["update"] = "green"
            except Exception:
                pass
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            test_file = self.data_dir / "write_test.tmp"
            with open(test_file, "w") as f:
                f.write("test")
            test_file.unlink()
            status["storage"] = "green"
        except Exception:
            pass
        return status

    def _xor_cipher(self, data: str) -> str:
        key = hashlib.sha256(self.hwid.encode()).hexdigest()
        key_len = len(key)
        cipher_chars = []
        for i, char in enumerate(data):
            key_char = key[i % key_len]
            cipher_chars.append(chr(ord(char) ^ ord(key_char)))
        return "".join(cipher_chars)

    def save_credentials(self, auth_type: str, key_or_user: str, password: Optional[str] = None):
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "type": auth_type,
                "key_or_user": key_or_user,
                "password": password or ""
            }
            raw_json = json.dumps(payload)
            encrypted_data = self._xor_cipher(raw_json)
            with open(self.credentials_file, "w", encoding="utf-8", newline="") as f:
                f.write(encrypted_data)
        except Exception as e:
            logger.error(f"Failed to cache credentials: {e}")

    def load_cached_credentials(self) -> Optional[Dict[str, str]]:
        if not self.credentials_file.exists():
            return None
        try:
            with open(self.credentials_file, "r", encoding="utf-8", newline="") as f:
                encrypted_data = f.read()
            if not encrypted_data:
                return None
            raw_json = self._xor_cipher(encrypted_data)
            return json.loads(raw_json)
        except Exception:
            self.delete_cached_credentials()
        return None

    def delete_cached_credentials(self):
        try:
            if self.credentials_file.exists():
                self.credentials_file.unlink()
        except Exception:
            pass

    def login_username_password(self, user: str, password: str, remember: bool = True) -> Dict[str, Any]:
        user = user.strip()
        password = password.strip()
        if not user or not password:
            raise ValueError("Credentials required.")
        payload = {
            "username": user,
            "password": password,
            "hwid": self.hwid
        }
        res = self._execute_request("POST", f"{self.server_url}/api/login", json=payload, timeout=10)
        try:
            res_data = res.json()
        except Exception:
            raise RuntimeError("Server response format error.")
        if res.status_code == 200 and res_data.get("success"):
            self.session_token = res_data.get("token", "")
            self.user_info = res_data.get("user_data", {})
            if remember:
                self.save_credentials("userpass", user, password)
            return self.user_info
        else:
            raise RuntimeError(res_data.get("message", "Login failed."))

    def register_user(self, user: str, password: str, invite_key: str = "", role: str = "user", init_secret: Optional[str] = None) -> Dict[str, Any]:
        user = user.strip()
        password = password.strip()
        if not user or not password:
            raise ValueError("All fields are required.")
        payload = {
            "username": user,
            "password": password,
            "hwid": self.hwid,
            "role": role,
            "invite_key": invite_key
        }
        headers = {}
        if init_secret:
            headers["X-Init-Secret"] = init_secret
        res = self._execute_request("POST", f"{self.server_url}/api/register", json=payload, headers=headers, timeout=10)
        try:
            res_data = res.json()
        except Exception:
            raise RuntimeError("Server response format error.")
        if res.status_code == 201 and res_data.get("success"):
            return self.login_username_password(user, password, remember=True)
        else:
            raise RuntimeError(res_data.get("message", "Registration failed."))

    def get_or_create_local_session(self) -> Dict[str, Any]:
        try:
            payload = {"hwid": self.hwid}
            res = self._execute_request(
                "POST", f"{self.server_url}/api/local-session", json=payload, timeout=4
            )
            if res.status_code == 200:
                data = res.json()
                if data.get("success"):
                    self.session_token = data.get("token", "")
                    self.user_info = data.get("user_data", {})
                    return {
                        "success": True,
                        "token": self.session_token,
                        "user_data": self.user_info
                    }
        except Exception as e:
            logger.debug(f"Local session endpoint not available or server offline: {e}")

        self.session_token = "local_standalone_token"
        self.user_info = {
            "username": "Local User",
            "ip": "127.0.0.1",
            "hwid": self.hwid,
            "role": "user",
            "expires": "Never (Lifetime)",
            "createdate": "Local System",
            "lastlogin": "Active",
            "subscription": "Local Edition",
            "credits": 9999,
            "credits_unlimited": True,
            "lifetime_requests": 0
        }
        return {
            "success": True,
            "token": self.session_token,
            "user_data": self.user_info
        }

    def get_remaining_days(self) -> int:
        return 9999

    def get_announcements(self) -> str:
        try:
            res = self._execute_request("GET", f"{self.server_url}/api/announcements", timeout=5)
            if res.status_code == 200:
                return res.json().get("announcements", "")
        except Exception:
            pass
        return "No updates."

    def _get_admin_headers(self) -> Dict[str, str]:
        if not self.session_token:
            raise PermissionError("Session expired.")
        return {
            "Authorization": f"Bearer {self.session_token}",
            "Content-Type": "application/json"
        }

    def admin_get_users(self) -> List[Dict[str, Any]]:
        headers = self._get_admin_headers()
        res = self._execute_request("GET", f"{self.server_url}/api/admin/users", headers=headers, timeout=10)
        try:
            res_data = res.json()
        except Exception:
            raise RuntimeError("Format error.")
        if res.status_code == 200:
            return res_data
        raise RuntimeError(res_data.get("message", "Error loading user list."))

    def admin_create_user(self, username: str, password: str, role: str = "user") -> str:
        headers = self._get_admin_headers()
        payload = {"username": username, "password": password, "role": role}
        res = self._execute_request("POST", f"{self.server_url}/api/admin/users", json=payload, headers=headers, timeout=10)
        try:
            res_data = res.json()
        except Exception:
            raise RuntimeError("Format error.")
        if res.status_code == 200:
            return res_data.get("message", "Success.")
        raise RuntimeError(res_data.get("message", "Error."))

    def admin_delete_user(self, username: str) -> str:
        headers = self._get_admin_headers()
        res = self._execute_request("DELETE", f"{self.server_url}/api/admin/users/{username}", headers=headers, timeout=10)
        try:
            res_data = res.json()
        except Exception:
            raise RuntimeError("Format error.")
        if res.status_code == 200:
            return res_data.get("message", "Success.")
        raise RuntimeError(res_data.get("message", "Error."))

    def admin_reset_password(self, username: str, password: str) -> str:
        headers = self._get_admin_headers()
        payload = {"username": username, "password": password}
        res = self._execute_request("POST", f"{self.server_url}/api/admin/reset-password", json=payload, headers=headers, timeout=10)
        try:
            res_data = res.json()
        except Exception:
            raise RuntimeError("Format error.")
        if res.status_code == 200:
            return res_data.get("message", "Success.")
        raise RuntimeError(res_data.get("message", "Error."))

    def admin_reset_hwid(self, username: str) -> str:
        headers = self._get_admin_headers()
        payload = {"username": username}
        res = self._execute_request("POST", f"{self.server_url}/api/admin/reset-hwid", json=payload, headers=headers, timeout=10)
        try:
            res_data = res.json()
        except Exception:
            raise RuntimeError("Format error.")
        if res.status_code == 200:
            return res_data.get("message", "Success.")
        raise RuntimeError(res_data.get("message", "Error."))

    def admin_ban_user(self, username: str, banned: bool) -> str:
        headers = self._get_admin_headers()
        payload = {"username": username, "banned": 1 if banned else 0}
        res = self._execute_request("POST", f"{self.server_url}/api/admin/ban", json=payload, headers=headers, timeout=10)
        try:
            res_data = res.json()
        except Exception:
            raise RuntimeError("Format error.")
        if res.status_code == 200:
            return res_data.get("message", "Success.")
        raise RuntimeError(res_data.get("message", "Error."))

    def admin_set_version(self, version: str, download_url: str, changelog: str, announcements: str) -> str:
        headers = self._get_admin_headers()
        payload = {
            "version": version,
            "download_url": download_url,
            "changelog": changelog,
            "announcements": announcements
        }
        res = self._execute_request("POST", f"{self.server_url}/api/admin/version", json=payload, headers=headers, timeout=10)
        try:
            res_data = res.json()
        except Exception:
            raise RuntimeError("Format error.")
        if res.status_code == 200:
            return res_data.get("message", "Success.")
        raise RuntimeError(res_data.get("message", "Error."))

    def admin_get_invites(self) -> List[Dict[str, Any]]:
        headers = self._get_admin_headers()
        res = self._execute_request("GET", f"{self.server_url}/api/admin/invites", headers=headers, timeout=10)
        try:
            res_data = res.json()
        except Exception:
            raise RuntimeError("Format error.")
        if res.status_code == 200:
            return res_data
        raise RuntimeError(res_data.get("message", "Error."))

    def admin_create_invite(self) -> Dict[str, Any]:
        headers = self._get_admin_headers()
        res = self._execute_request("POST", f"{self.server_url}/api/admin/invites", headers=headers, timeout=10)
        try:
            res_data = res.json()
        except Exception:
            raise RuntimeError("Format error.")
        if res.status_code == 200:
            return res_data
        raise RuntimeError(res_data.get("message", "Error."))

    def admin_delete_invite(self, key: str) -> str:
        headers = self._get_admin_headers()
        res = self._execute_request("DELETE", f"{self.server_url}/api/admin/invites/{key}", headers=headers, timeout=10)
        try:
            res_data = res.json()
        except Exception:
            raise RuntimeError("Format error.")
        if res.status_code == 200:
            return res_data.get("message", "Success.")
        raise RuntimeError(res_data.get("message", "Error."))

    def admin_get_audit_logs(self) -> List[Dict[str, Any]]:
        headers = self._get_admin_headers()
        res = self._execute_request("GET", f"{self.server_url}/api/admin/audit-logs", headers=headers, timeout=10)
        try:
            res_data = res.json()
        except Exception:
            raise RuntimeError("Format error.")
        if res.status_code == 200:
            return res_data
        raise RuntimeError(res_data.get("message", "Error."))

    def admin_get_login_history(self) -> List[Dict[str, Any]]:
        headers = self._get_admin_headers()
        res = self._execute_request("GET", f"{self.server_url}/api/admin/login-history", headers=headers, timeout=10)
        try:
            res_data = res.json()
        except Exception:
            raise RuntimeError("Format error.")
        if res.status_code == 200:
            return res_data
        raise RuntimeError(res_data.get("message", "Error."))

KeyAuthHandler = AuthClient

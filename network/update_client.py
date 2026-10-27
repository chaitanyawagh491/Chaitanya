import logging
import sys
import os
import requests
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from config import config
from utils.alerts import NotificationManager

logger = logging.getLogger("SystemUpdater")

class SystemUpdater:
    def __init__(self, current_version: str, notifier: NotificationManager, server_url: str):
        self.current_version = current_version
        self.notifier = notifier
        self.server_url = server_url.rstrip('/')

    def check_and_apply_update(self) -> bool:
        try:
            res = requests.get(f"{self.server_url}/api/update?version={self.current_version}", timeout=8)
            if res.status_code != 200:
                return False
            data = res.json()
            if not data.get("update_available"):
                return False
            latest_version = data.get("latest_version", "N/A")
            download_url = data.get("download_url", "")
            self.notifier.notify_update_available(latest_version)
            if download_url:
                self.trigger_silent_upgrade(download_url, latest_version)
                return True
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
        return False

    def trigger_silent_upgrade(self, download_url: str, new_version: str):
        try:
            res = requests.get(download_url, timeout=30)
            if res.status_code != 200:
                raise RuntimeError(f"Failed to download update: HTTP {res.status_code}")
            zip_data = res.content
            import tempfile
            temp_dir = Path(tempfile.gettempdir())
            temp_zip = temp_dir / "portal_update.zip"
            with open(temp_zip, "wb") as f:
                f.write(zip_data)
            batch_content = f"""@echo off
timeout /t 1 /nobreak > nul
powershell -Command "Expand-Archive -Path '{temp_zip.resolve()}' -DestinationPath '.' -Force"
del "{temp_zip.resolve()}"
start "" "pythonw.exe" "main.py"
del "%~f0"
exit
"""
            batch_file = temp_dir / "update_installer.bat"
            with open(batch_file, "w", encoding="utf-8") as f:
                f.write(batch_content)
            subprocess.Popen(["cmd.exe", "/c", str(batch_file.resolve())], creationflags=0x00000008)
            sys.exit(0)
        except Exception as e:
            logger.error(f"Upgrade failed: {e}")
            self.notifier.send_notification("Update Failed", f"Failed to install update {new_version}.")

    def get_changelog(self) -> str:
        try:
            res = requests.get(f"{self.server_url}/api/changelog", timeout=5)
            if res.status_code == 200:
                return f"=== RELEASE NOTES ===\n\n{res.text}"
        except Exception:
            pass
        return "=== RELEASE NOTES ===\n\nFailed to retrieve changelog."

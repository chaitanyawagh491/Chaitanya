import os
import sys
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from config import config

logger = logging.getLogger("EnvService")

class EnvService:
    def __init__(self):
        self.status = "READY"
        self.progress = 100.0
        self.progress_msg = "Ready"
        self._on_status_change: Optional[Callable[[str, float, str], None]] = None

    def set_callback(self, callback: Callable[[str, float, str], None]) -> None:
        self._on_status_change = callback

    def _update_status(self, status: str, progress: float, message: str) -> None:
        self.status = status
        self.progress = progress
        self.progress_msg = message
        if self._on_status_change:
            try:
                self._on_status_change(status, progress, message)
            except Exception:
                pass

    @staticmethod
    def verify_python_libs() -> Dict[str, bool]:
        libs = {
            "customtkinter": False,
            "cv2": False,
            "numpy": False,
            "PIL": False,
            "requests": False,
            "pynput": False
        }
        for lib in list(libs.keys()):
            try:
                __import__(lib)
                libs[lib] = True
            except ImportError:
                libs[lib] = False
        return libs

    def verify_environment(self) -> Dict[str, Any]:
        libs = self.verify_python_libs()
        libs_ok = all(libs.values())
        storage_ok = False
        try:
            config.LOG_DIR.mkdir(parents=True, exist_ok=True)
            test_file = config.LOG_DIR / ".dep_write_test"
            test_file.write_text("ok")
            test_file.unlink()
            storage_ok = True
        except Exception:
            storage_ok = False
        is_healthy = libs_ok and storage_ok
        self.status = "READY" if is_healthy else "FAILED"
        return {
            "healthy": is_healthy,
            "libraries": libs,
            "storage": storage_ok
        }

DependencyService = EnvService

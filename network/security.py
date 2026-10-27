import time
import logging
import json
import hashlib
from pathlib import Path

logger = logging.getLogger("Security")

class SecurityManager:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.integrity_file = data_dir / "sec.dat"
        self.config_file = data_dir / "settings.json"

    def check_clock_rollback(self) -> bool:
        current_time = int(time.time())
        if not self.integrity_file.exists():
            self.save_security_metadata(current_time)
            return False
        try:
            with open(self.integrity_file, "r") as f:
                data = json.load(f)
                last_run = data.get("last_run", 0)
        except Exception:
            return True
        if current_time < last_run:
            return True
        self.save_security_metadata(current_time)
        return False

    def save_security_metadata(self, current_time: int):
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "last_run": current_time,
                "token": hashlib.sha256(str(current_time).encode()).hexdigest()
            }
            with open(self.integrity_file, "w") as f:
                json.dump(payload, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save security metadata: {e}")

    def verify_config_integrity(self) -> bool:
        if not self.config_file.exists():
            return True
        try:
            with open(self.config_file, "r") as f:
                json.load(f)
            return True
        except json.JSONDecodeError:
            return False

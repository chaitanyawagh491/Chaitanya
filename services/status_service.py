import logging
import requests
from pathlib import Path
from typing import Dict

from config import config

logger = logging.getLogger("StatusService")

HEALTH_DISPLAY_LABELS: Dict[str, str] = {
    "internet":      "Internet",
    "server":        "Auth Server",
    "database":      "Database",
    "visual_system": "Visual System",
    "ai_engine":     "AI Engine",
    "storage":       "Storage",
    "update":        "Update Service",
}

def check_all() -> Dict[str, str]:
    status = {key: "red" for key in HEALTH_DISPLAY_LABELS}
    status["storage"] = "red"
    try:
        res = requests.get("https://1.1.1.1", timeout=3)
        status["internet"] = "green" if res.status_code == 200 else "yellow"
    except Exception:
        status["internet"] = "red"
    
    if status["internet"] == "green":
        try:
            res = requests.get(f"{config.AUTH_SERVER_URL}/api/ping", timeout=5)
            if res.status_code == 200:
                status["server"] = "green"
                data = res.json()
                status["database"] = "green" if data.get("database") == "connected" else "red"
            else:
                status["server"] = "red"
                status["database"] = "red"
        except Exception:
            status["server"] = "red"
            status["database"] = "red"
    else:
        status["server"] = "red"
        status["database"] = "red"

    # Visual system is nominal if capture is functional
    try:
        from PIL import ImageGrab
        screenshot = ImageGrab.grab(bbox=(0, 0, 1, 1))
        if screenshot and screenshot.size[0] > 0:
            status["visual_system"] = "green"
        else:
            status["visual_system"] = "yellow"
    except Exception:
        status["visual_system"] = "red"

    if status["internet"] == "green" and config.has_primary_key():
        status["ai_engine"] = "green"
    elif not config.has_primary_key():
        status["ai_engine"] = "yellow"
    else:
        status["ai_engine"] = "red"

    if status["internet"] == "green" and status["server"] == "green":
        try:
            res = requests.get(
                f"{config.AUTH_SERVER_URL}/api/update?version={config.CURRENT_VERSION}",
                timeout=4
            )
            status["update"] = "green" if res.status_code == 200 else "red"
        except Exception:
            status["update"] = "red"
    else:
        status["update"] = "red"

    try:
        config.LOG_DIR.mkdir(parents=True, exist_ok=True)
        test_file = config.LOG_DIR / ".status_write_test"
        test_file.write_text("ok")
        test_file.unlink()
        status["storage"] = "green"
    except Exception:
        status["storage"] = "red"

    return status

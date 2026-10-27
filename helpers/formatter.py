import json
from typing import Any, Dict

class TextFormatter:
    @staticmethod
    def format_bytes(b: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if b < 1024.0:
                return f"{b:.2f} {unit}"
            b /= 1024.0
        return f"{b:.2f} TB"

    @staticmethod
    def strip_control_chars(text: str) -> str:
        return "".join(c for c in text if ord(c) >= 32 or c in "\n\r\t")

    @staticmethod
    def to_json(obj: Any) -> str:
        return json.dumps(obj, default=str)

    @staticmethod
    def from_json(data: str) -> Dict[str, Any]:
        try:
            return json.loads(data)
        except Exception:
            return {}

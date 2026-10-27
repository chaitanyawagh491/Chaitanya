from typing import List

_safe_mode_active = False
_failure_reasons: List[str] = []

def enable(reasons: List[str] = None) -> None:
    global _safe_mode_active, _failure_reasons
    _safe_mode_active = True
    _failure_reasons = reasons or ["System initialization failure."]
    from config import config
    config.SAFE_MODE = True

def disable() -> None:
    global _safe_mode_active, _failure_reasons
    _safe_mode_active = False
    _failure_reasons = []
    from config import config
    config.SAFE_MODE = False

def is_active() -> bool:
    return _safe_mode_active

def get_reasons() -> List[str]:
    return list(_failure_reasons)

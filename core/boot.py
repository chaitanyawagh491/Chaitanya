import logging
import time
from datetime import datetime
from typing import Optional, List, Dict
from utils.log import log_exception, add_recent_event

logger = logging.getLogger("Boot")

class BootSequence:
    def __init__(self, version: str):
        self.version = version
        self._phases: List[Dict] = []
        self._current_phase: Optional[str] = None
        self._failed = False
        self._start_time = 0.0
        add_recent_event(f"System boot sequence initiated (v{version})")

    def begin(self, phase_name: str) -> None:
        self._current_phase = phase_name
        self._start_time = time.time()
        add_recent_event(f"Boot phase: {phase_name}")

    def ok(self, message: str = "") -> None:
        phase = self._current_phase or "Unknown"
        duration = int((time.time() - self._start_time) * 1000)
        msg = f" -- {message}" if message else ""
        logger.info(f"[BOOT] OK  {phase}{msg} ({duration}ms)")
        self._phases.append({"phase": phase, "status": "ok", "message": f"{message} ({duration}ms)"})

    def warn(self, message: str) -> None:
        phase = self._current_phase or "Unknown"
        duration = int((time.time() - self._start_time) * 1000)
        logger.warning(f"[BOOT] WARN {phase} -- {message} ({duration}ms)")
        self._phases.append({"phase": phase, "status": "warn", "message": f"{message} ({duration}ms)"})
        add_recent_event(f"Boot warning: {phase}: {message} ({duration}ms)")

    def fail(self, message: str, exc: Optional[Exception] = None) -> None:
        phase = self._current_phase or "Unknown"
        self._failed = True
        duration = int((time.time() - self._start_time) * 1000)
        if exc:
            log_exception(logger, "Boot", phase, exc, extra_context=f"{message} ({duration}ms)")
        else:
            logger.error(f"[BOOT] FAIL {phase} -- {message} ({duration}ms)")
        self._phases.append({
            "phase": phase,
            "status": "fail",
            "message": f"{message} ({duration}ms)",
            "error": str(exc) if exc else None
        })
        add_recent_event(f"Boot FAILED: {phase}: {message} ({duration}ms)")

    def is_healthy(self) -> bool:
        return not self._failed

    def get_failed_phases(self) -> List[Dict]:
        return [p for p in self._phases if p["status"] == "fail"]

    def summary(self) -> None:
        total = len(self._phases)
        failed = len(self.get_failed_phases())
        warnings = len([p for p in self._phases if p["status"] == "warn"])
        if self._failed:
            logger.error(f"[BOOT] COMPLETED WITH FAILURES -- {total} phases, {failed} failed, {warnings} warnings")
        else:
            logger.info(f"[BOOT] COMPLETE -- {total} phases, {warnings} warnings, 0 failures")
        add_recent_event(f"Boot complete: {'FAILED' if self._failed else 'OK'} ({total} phases)")

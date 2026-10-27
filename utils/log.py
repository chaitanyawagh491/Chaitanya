import logging
import logging.handlers
import sys
import traceback
from pathlib import Path
from datetime import datetime

class SensitiveInfoFormatter(logging.Formatter):
    def format(self, record):
        formatted = super().format(record)
        try:
            from config import config
            if getattr(config, "AUTH_SERVER_URL", None):
                formatted = formatted.replace(config.AUTH_SERVER_URL, "[AUTH_SERVER_URL]")
            api_keys = getattr(config, "API_KEYS", {})
            if isinstance(api_keys, dict):
                for key_val in api_keys.values():
                    if key_val and isinstance(key_val, str) and len(key_val) > 4:
                        formatted = formatted.replace(key_val, "[REDACTED_API_KEY]")
            for legacy_attr in ("USER_API_KEY", "_PRIMARY_API_KEY", "_FALLBACK_API_KEY"):
                val = getattr(config, legacy_attr, None)
                if val and isinstance(val, str):
                    formatted = formatted.replace(val, "[REDACTED_API_KEY]")
        except Exception:
            pass
        return formatted

def setup_logger(log_file: Path, debug_mode: bool = False) -> None:
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        level = logging.DEBUG if debug_mode else logging.INFO
        root = logging.getLogger()
        root.setLevel(level)
        if root.handlers:
            root.handlers.clear()
        formatter = SensitiveInfoFormatter(
            "%(asctime)s | %(levelname)-8s | [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        root.addHandler(file_handler)
        stream = sys.stdout or sys.stderr
        if stream is not None:
            try:
                import io
                utf8_stream = io.TextIOWrapper(
                    stream.buffer if hasattr(stream, 'buffer') else stream,
                    encoding='utf-8',
                    errors='replace',
                    line_buffering=True
                )
                stream_handler = logging.StreamHandler(utf8_stream)
            except (AttributeError, Exception):
                stream_handler = logging.StreamHandler(stream)
                stream_handler.stream.errors = 'replace'
            stream_handler.setFormatter(formatter)
            stream_handler.setLevel(level)
            root.addHandler(stream_handler)
        logger = logging.getLogger("Logger")
        logger.info(f"Logging initialized. Level={'DEBUG' if debug_mode else 'INFO'}, File={log_file}")
    except Exception as e:
        _safe_stderr(f"FATAL: Failed to setup logger: {e}")

def log_exception(
    logger: logging.Logger,
    module: str,
    function: str,
    error: Exception,
    extra_context: str = "",
) -> None:
    tb = traceback.format_exc()
    context_str = f" | Context: {extra_context}" if extra_context else ""
    logger.error(f"[{module}] [{function}] {type(error).__name__}: {error}{context_str}\n{tb}")

def write_crash_report(
    crash_log_file: Path,
    version: str,
    module: str,
    function: str,
    error: Exception,
    recent_events: list[str] = None,
) -> Path:
    import platform
    import os
    try:
        crash_log_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            username = os.getlogin()
        except Exception:
            import getpass
            username = getpass.getuser()
        os_info = platform.platform()
        if sys.platform == "win32":
            rel, ver, _, _ = platform.win32_ver()
            os_info = f"Windows {rel} (Build {ver})"
        tb = traceback.format_exc()
        events_block = ""
        if recent_events:
            events_block = "\nRECENT EVENTS:\n"
            for event in recent_events[-20:]:
                events_block += f"  {event}\n"
        report = f"""================================================================
           PORTAL CLIENT — CRASH REPORT
           Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
================================================================

APPLICATION:
  Version:     {version}
  OS:          {os_info}
  User:        {username}
  Architecture:{platform.machine()} ({platform.architecture()[0]})

CRASH LOCATION:
  Module:      {module}
  Function:    {function}
  Error Type:  {type(error).__name__}
  Error:       {error}

FULL TRACEBACK:
{tb}{events_block}
================================================================
                     END OF CRASH REPORT
================================================================
"""
        try:
            from config import config
            if getattr(config, "AUTH_SERVER_URL", None):
                report = report.replace(config.AUTH_SERVER_URL, "[AUTH_SERVER_URL]")
            api_keys = getattr(config, "API_KEYS", {})
            if isinstance(api_keys, dict):
                for key_val in api_keys.values():
                    if key_val and isinstance(key_val, str) and len(key_val) > 4:
                        report = report.replace(key_val, "[REDACTED_API_KEY]")
            for legacy_attr in ("USER_API_KEY", "_PRIMARY_API_KEY", "_FALLBACK_API_KEY"):
                val = getattr(config, legacy_attr, None)
                if val and isinstance(val, str):
                    report = report.replace(val, "[REDACTED_API_KEY]")
        except Exception:
            pass
        with open(crash_log_file, "a", encoding="utf-8") as f:
            f.write(report)
        return crash_log_file
    except Exception as write_error:
        _safe_stderr(f"Failed to write crash report: {write_error}")
        return crash_log_file

_crash_log_path: Path = None
_app_version: str = "3.0.0"
_recent_events: list = []
_base_logger = logging.getLogger("CrashHook")

def _safe_stderr(msg: str) -> None:
    try:
        if sys.stderr is not None:
            print(msg, file=sys.stderr)
        elif sys.stdout is not None:
            print(msg, file=sys.stdout)
    except Exception:
        pass

def configure_crash_hook(crash_log_file: Path, version: str) -> None:
    global _crash_log_path, _app_version
    _crash_log_path = crash_log_file
    _app_version = version
    sys.excepthook = _global_exception_hook
    _base_logger.info("Global crash hook registered.")

def add_recent_event(event: str) -> None:
    global _recent_events
    timestamp = datetime.now().strftime("%H:%M:%S")
    _recent_events.append(f"[{timestamp}] {event}")
    if len(_recent_events) > 50:
        _recent_events = _recent_events[-50:]

def _global_exception_hook(exc_type, exc_value, exc_traceback) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    _base_logger.critical("UNHANDLED EXCEPTION — Application crash!", exc_info=(exc_type, exc_value, exc_traceback))
    if _crash_log_path:
        try:
            tb = traceback.extract_tb(exc_traceback)
            if tb:
                last_frame = tb[-1]
                module = Path(last_frame.filename).stem
                function = last_frame.name
            else:
                module = "Unknown"
                function = "Unknown"
            write_crash_report(
                crash_log_file=_crash_log_path,
                version=_app_version,
                module=module,
                function=function,
                error=exc_value,
                recent_events=_recent_events,
            )
            _base_logger.info(f"Crash report written to: {_crash_log_path}")
        except Exception as e:
            _safe_stderr(f"Failed to write crash log: {e}")
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

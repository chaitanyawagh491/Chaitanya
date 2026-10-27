import os
import sys
import logging
import ctypes

logger = logging.getLogger(__name__)

class VisibilityController:
    @staticmethod
    def hide_console() -> None:
        try:
            if sys.platform == "win32":
                hwnd = ctypes.windll.kernel32.GetConsoleWindow()
                if hwnd != 0:
                    ctypes.windll.user32.ShowWindow(hwnd, 0)
        except Exception as e:
            logger.warning(f"Could not hide console: {e}")

    @staticmethod
    def hide_from_taskbar() -> None:
        pass

    @staticmethod
    def set_low_priority() -> None:
        try:
            if sys.platform == "win32":
                import psutil
                p = psutil.Process()
                p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        except Exception as e:
            logger.warning(f"Could not set process priority: {e}")
            
class ProcessHider(VisibilityController):
    pass

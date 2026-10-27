import sys
import ctypes
import logging

logger = logging.getLogger(__name__)

class ProcessHider:
    @staticmethod
    def hide_console() -> None:
        try:
            if sys.platform == "win32":
                hwnd = ctypes.windll.kernel32.GetConsoleWindow()
                if hwnd != 0:
                    ctypes.windll.user32.ShowWindow(hwnd, 0)
        except Exception as e:
            logger.warning(str(e))

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
            logger.warning(str(e))

import logging
import tkinter as tk
from typing import Optional
from PIL import Image, ImageGrab
from config import Config

logger = logging.getLogger(__name__)

class ScreenCaptureManager:
    def __init__(self, config: Config, parent=None):
        self.config = config
        self.parent = parent

    def request_screen_selection(self, parent=None):
        has_root = False
        try:
            if tk._default_root is not None:
                has_root = True
        except Exception:
            pass
        if parent:
            root = tk.Toplevel(parent)
        elif has_root:
            root = tk.Toplevel(tk._default_root)
        else:
            root = tk.Tk()
        root.attributes("-alpha", 0.3)
        root.attributes("-fullscreen", True)
        root.attributes("-topmost", True)
        root.config(cursor="cross")
        canvas = tk.Canvas(root, cursor="cross", bg="grey")
        canvas.pack(fill="both", expand=True)
        start_x = start_y = cur_rect = None

        def on_button_press(event):
            nonlocal start_x, start_y
            start_x, start_y = event.x, event.y

        def on_move_press(event):
            nonlocal cur_rect
            if cur_rect:
                canvas.delete(cur_rect)
            cur_rect = canvas.create_rectangle(start_x, start_y, event.x, event.y, outline="red", width=3)

        def on_button_release(event):
            end_x, end_y = event.x, event.y
            x1, x2 = min(start_x, end_x), max(start_x, end_x)
            y1, y2 = min(start_y, end_y), max(start_y, end_y)
            if (x2 - x1) > 20 and (y2 - y1) > 20:
                self.config.CROP_BOX = [x1, y1, x2, y2]
                self.config.save_to_disk()
            root.destroy()

        def on_escape(event):
            root.destroy()

        canvas.bind("<ButtonPress-1>", on_button_press)
        canvas.bind("<B1-Motion>", on_move_press)
        canvas.bind("<ButtonRelease-1>", on_button_release)
        root.bind("<Escape>", on_escape)
        if has_root or parent:
            root.wait_window(root)
        else:
            root.mainloop()

    def _get_screen_dimensions(self) -> tuple[int, int]:
        try:
            import sys
            if sys.platform == "win32":
                import ctypes
                w = ctypes.windll.user32.GetSystemMetrics(0)
                h = ctypes.windll.user32.GetSystemMetrics(1)
                if w > 0 and h > 0:
                    return w, h
        except Exception:
            pass
        try:
            if self.parent and hasattr(self.parent, "winfo_screenwidth"):
                return self.parent.winfo_screenwidth(), self.parent.winfo_screenheight()
        except Exception:
            pass
        try:
            return ImageGrab.grab(bbox=(0, 0, 1, 1)).size
        except Exception:
            return 1920, 1080

    def is_crop_box_valid(self, crop_box) -> bool:
        if not crop_box or len(crop_box) != 4:
            return False
        try:
            screen_w, screen_h = self._get_screen_dimensions()
            x1, y1, x2, y2 = crop_box
            return (0 <= x1 < x2 <= screen_w) and (0 <= y1 < y2 <= screen_h)
        except Exception:
            return False


    def capture_screen(self) -> Optional[Image.Image]:
        try:
            if self.config.CROP_BOX:
                if self.is_crop_box_valid(self.config.CROP_BOX):
                    return ImageGrab.grab(bbox=self.config.CROP_BOX)
                else:
                    logger.warning(f"Configured crop box {self.config.CROP_BOX} is invalid for current display resolution.")
                    import threading
                    if threading.current_thread() is threading.main_thread():
                        self.request_screen_selection()
                        if self.config.CROP_BOX and self.is_crop_box_valid(self.config.CROP_BOX):
                            return ImageGrab.grab(bbox=self.config.CROP_BOX)
                    else:
                        logger.info("Background thread capture: falling back to full screen to prevent cross-thread GUI call.")
            return ImageGrab.grab()
        except Exception as e:
            logger.error(f"Capture failed: {e}")
            return None

import logging
import tkinter as tk
import threading
import sys
from config import Config

logger = logging.getLogger(__name__)

class OverlayController:
    def __init__(self, config: Config, parent=None):
        self.config = config
        self.parent = parent
        self._current_window = None

    def inject_response(self, text: str) -> bool:
        return self.display_response(text)

    def inject_overlay(self, text: str) -> bool:
        return self.display_response(text)

    def display_status(self, text: str) -> bool:
        """Display a temporary status notification (e.g. 'Analyzing...') at top-left."""
        return self._dispatch_overlay(text, text_color="#818CF8", duration_ms=25000)

    def display_error(self, error_text: str) -> bool:
        """Display an error notification at top-left of the screen."""
        clean_text = error_text.strip() if error_text else "AI analysis failed."
        if not clean_text.startswith("⚠"):
            clean_text = f"⚠ {clean_text}"
        duration_ms = max(5000, int(self.config.RESPONSE_DURATION * 1500))
        return self._dispatch_overlay(clean_text, text_color="#F87171", duration_ms=duration_ms)

    def display_response(self, text: str) -> bool:
        """Display the actual AI answer at top-left of the screen."""
        clean_token = text.strip() if text else "?"
        hex_color = '#%02x%02x%02x' % tuple(self.config.RESPONSE_TEXT_COLOR)
        if hex_color.lower() in ["#000000", "#0a0a0a"]:
            hex_color = "#4ADE80"
        duration_ms = max(3000, int(self.config.RESPONSE_DURATION * 1000))
        return self._dispatch_overlay(clean_token, text_color=hex_color, duration_ms=duration_ms)

    def _dispatch_overlay(self, text: str, text_color: str, duration_ms: int) -> bool:
        try:
            logger.debug(f"Dispatching overlay text: {text[:60]}")
            if self.parent and hasattr(self.parent, "after"):
                self.parent.after(0, lambda: self._show_overlay(text, text_color, duration_ms))
            else:
                overlay_thread = threading.Thread(
                    target=self._show_overlay,
                    args=(text, text_color, duration_ms),
                    daemon=True,
                    name="OverlayWorker"
                )
                overlay_thread.start()
            return True
        except Exception as e:
            logger.error(f"Overlay dispatch failed: {e}")
            return False

    def _close_existing(self):
        if self._current_window:
            try:
                if self._current_window.winfo_exists():
                    self._current_window.destroy()
            except Exception:
                pass
            self._current_window = None

    def _show_overlay(self, text: str, text_color: str, duration_ms: int):
        self._close_existing()
        try:
            if self.parent and hasattr(self.parent, "winfo_exists") and self.parent.winfo_exists():
                root = tk.Toplevel(self.parent)
            elif tk._default_root is not None and tk._default_root.winfo_exists():
                root = tk.Toplevel(tk._default_root)
            else:
                root = tk.Tk()

            self._current_window = root
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            root.wm_attributes("-transparentcolor", "black")
            root.config(bg="black")

            font_size = max(11, int(self.config.RESPONSE_FONT_SIZE))
            font_config = ("Segoe UI Variable", font_size, "bold")

            # Resolve screen dimensions for wrapping
            screen_w = 1920
            try:
                if sys.platform == "win32":
                    import ctypes
                    screen_w = ctypes.windll.user32.GetSystemMetrics(0) or 1920
            except Exception:
                pass

            x_pos = max(10, self.config.INJECT_X)
            y_pos = max(10, self.config.INJECT_Y)
            max_wrap = min(800, max(360, screen_w - x_pos - 40))

            label = tk.Label(
                root,
                text=text,
                font=font_config,
                fg=text_color,
                bg="black",
                justify="left",
                wraplength=max_wrap
            )
            label.pack(padx=10, pady=6, anchor="nw")
            root.update_idletasks()

            width = max(80, label.winfo_reqwidth() + 20)
            height = max(34, label.winfo_reqheight() + 12)
            root.geometry(f"{width}x{height}+{x_pos}+{y_pos}")

            self._apply_styles(root)
            root.after(duration_ms, lambda: self._safe_destroy(root))

            if not self.parent and (tk._default_root is None or tk._default_root == root):
                root.mainloop()
        except Exception as e:
            logger.error(f"Overlay rendering exception: {e}")

    def _safe_destroy(self, root: tk.Tk):
        try:
            if root and root.winfo_exists():
                root.destroy()
            if self._current_window == root:
                self._current_window = None
        except Exception:
            pass

    def _apply_styles(self, root: tk.Tk):
        if sys.platform != 'win32':
            return
        import ctypes
        try:
            root.update()
            hwnd = root.winfo_id()
            GWL_EXSTYLE = -20
            WS_EX_TRANSPARENT = 0x00000020
            WS_EX_NOACTIVATE = 0x08000000
            WS_EX_LAYERED = 0x00080000
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            new_style = style | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_LAYERED
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
            ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, 255, 1)

            if not self.config.DISABLE_CAPTURE_PROTECTION:
                WDA_EXCLUDEFROMCAPTURE = 0x00000011
                ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)

            HWND_TOPMOST = -1
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOACTIVATE = 0x0010
            SWP_SHOWWINDOW = 0x0040
            ctypes.windll.user32.SetWindowPos(
                hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW
            )
        except Exception as e:
            logger.error(f"Failed to apply overlay styles: {e}")

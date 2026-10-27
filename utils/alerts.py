import logging
import sys
from typing import Optional
import tkinter as tk

logger = logging.getLogger("Notifications")

class CustomToast(tk.Toplevel):
    def __init__(self, title: str, message: str, duration_ms: int = 2500):
        super().__init__()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.0)
        self.configure(bg="#111115")
        try:
            self.scaling_factor = self.winfo_fpixels('1i') / 96.0
        except Exception:
            self.scaling_factor = 1.0
        self.width = int(320 * self.scaling_factor)
        self.height = int(75 * self.scaling_factor)
        self.screen_width = self.winfo_screenwidth()
        self.target_x = self.screen_width - self.width - int(25 * self.scaling_factor)
        self.start_x = self.screen_width
        self.y = int(35 * self.scaling_factor)
        self.geometry(f"{self.width}x{self.height}+{self.start_x}+{self.y}")
        border_frame = tk.Frame(self, bg="#111115", highlightbackground="#BF5AF2", highlightthickness=1)
        border_frame.pack(fill="both", expand=True)
        lbl_title = tk.Label(
            border_frame, 
            text=f"✦ {title}", 
            font=("Segoe UI", int(11 * min(1.2, self.scaling_factor)), "bold") if self.scaling_factor > 1 else ("Segoe UI", 11, "bold"), 
            fg="#30D158", 
            bg="#111115", 
            anchor="w"
        )
        lbl_title.pack(fill="x", padx=int(15 * self.scaling_factor), pady=(int(8 * self.scaling_factor), 1))
        lbl_msg = tk.Label(
            border_frame, 
            text=message, 
            font=("Segoe UI", int(9 * min(1.2, self.scaling_factor))) if self.scaling_factor > 1 else ("Segoe UI", 9), 
            fg="#E5E5EA", 
            bg="#111115", 
            anchor="w",
            justify="left",
            wraplength=int(290 * self.scaling_factor)
        )
        lbl_msg.pack(fill="x", padx=int(15 * self.scaling_factor), pady=(0, int(8 * self.scaling_factor)))
        self.current_x = self.start_x
        self.alpha = 0.0
        self._animate_in()
        self.after(duration_ms, self._animate_out)

    def _animate_in(self):
        step_x = max(1, (self.current_x - self.target_x) // 3)
        self.current_x -= step_x
        if self.current_x < self.target_x:
            self.current_x = self.target_x
        if self.alpha < 0.95:
            self.alpha += 0.15
            if self.alpha > 0.95:
                self.alpha = 0.95
        self.attributes("-alpha", self.alpha)
        self.geometry(f"{self.width}x{self.height}+{self.current_x}+{self.y}")
        if self.current_x > self.target_x or self.alpha < 0.95:
            self.after(15, self._animate_in)

    def _animate_out(self):
        if self.alpha > 0.0:
            self.alpha -= 0.15
            if self.alpha < 0.0:
                self.alpha = 0.0
            self.current_x += int(15 * self.scaling_factor)
            self.attributes("-alpha", self.alpha)
            self.geometry(f"{self.width}x{self.height}+{self.current_x}+{self.y}")
            self.after(15, self._animate_out)
        else:
            self.destroy()

class NotificationManager:
    def __init__(self, app_name: str = "Visual Analyzer"):
        self.app_name = app_name

    def send_notification(self, title: str, message: str, icon_path: Optional[str] = None):
        logger.info(f"[Notification] {title}: {message}")
        try:
            if tk._default_root is not None:
                tk._default_root.after(0, lambda: CustomToast(title, message))
                return
        except Exception as e:
            logger.debug(f"Could not spawn custom Tkinter toast: {e}")
        print(f"\n*** ALERT ({title}) ***: {message}\n")

    def notify_activation_success(self, username: str):
        self.send_notification(
            title="Activation Success",
            message=f"Welcome back, {username}! Portal system is active."
        )

    def notify_license_expiry_warning(self, remaining_days: int):
        self.send_notification(
            title="License Expiration Notice",
            message=f"Your software license expires in {remaining_days} days. Please renew to preserve access."
        )

    def notify_update_available(self, new_version: str):
        self.send_notification(
            title="System Update Available",
            message=f"Version {new_version} is available. Go to dashboard to download."
        )

    def notify_connection_issue(self, error: str):
        self.send_notification(
            title="Network Connection Issue",
            message=f"Could not connect to licensing servers: {error}"
        )

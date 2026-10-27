import logging
import threading
import customtkinter as ctk
from pathlib import Path
from typing import Callable, Optional
import queue
import tkinter as tk

from config import config
from network.auth_client import KeyAuthHandler
from ui.components.side import Sidebar
from ui.views.diag import DiagnosticsView
from ui.views.login import AuthView
from ui.views.main import DashboardView
from ui.views.profile import AccountView
from ui.views.settings import PreferencesView
from ui.views.info import ReleaseNotesView
from ui.views.admin.portal import AdminView
import core.safe as safe_mode

logger = logging.getLogger("AppWindow")

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

_COLORS = {
    "bg":      "#0A0B10",
    "surface": "#12141C",
    "border":  "#252838",
    "text":    "#F3F4F6",
    "muted":   "#9CA3AF",
    "accent":  "#6366F1",
}

_main_thread = threading.current_thread()
_tkinter_after_queue = queue.Queue()
_orig_after = tk.Misc.after

def _thread_safe_after(self, ms, func=None, *args):
    if threading.current_thread() is _main_thread:
        return _orig_after(self, ms, func, *args)
    else:
        if func is not None:
            def task():
                try:
                    if self.winfo_exists():
                        _orig_after(self, ms, func, *args)
                except Exception:
                    pass
            _tkinter_after_queue.put(task)
            try:
                self.event_generate("<<ThreadSafeTask>>", when="tail")
            except Exception:
                pass
        return None

tk.Misc.after = _thread_safe_after

class ActivationWindow(ctk.CTk):
    def __init__(
        self,
        handler: KeyAuthHandler,
        on_authorized: Callable,
        on_start_engine: Optional[Callable] = None,
        on_stop_engine: Optional[Callable] = None,
        on_shortcut_changed: Optional[Callable] = None,
        on_logout: Optional[Callable] = None,
    ):
        super().__init__()
        self.handler = handler
        self.on_authorized = on_authorized
        self.on_start_engine = on_start_engine
        self.on_stop_engine = on_stop_engine
        self.on_shortcut_changed = on_shortcut_changed
        self.on_logout = on_logout
        self.user_data: dict = {}
        self.is_admin: bool = False
        self.logged_in: bool = False
        self.is_authenticated: bool = False
        self.engine_running: bool = False
        self._views: dict = {}
        self._credit_service = None
        self._current_tab: str = ""
        self._last_bg_size: Optional[tuple[int, int]] = None
        self._setup_window()
        self._setup_layout()
        self.bind("<<ThreadSafeTask>>", lambda e: self._process_after_queue(event=e))
        self._start()
        self._process_after_queue()

    def _process_after_queue(self, event=None):
        if not self.winfo_exists():
            return
        try:
            while True:
                task = _tkinter_after_queue.get_nowait()
                try:
                    task()
                except Exception as e:
                    logger.error(f"Error in thread-safe after task: {e}")
        except queue.Empty:
            pass
        if event is None:
            _orig_after(self, 150, self._process_after_queue)

    def _setup_window(self) -> None:
        self.title("Visual Analyzer")
        self.geometry("980x660")
        self.resizable(True, True)
        self.minsize(980, 640)
        self.configure(fg_color=_COLORS["bg"])
        icon_path = Path(__file__).parent / "icon.ico"
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:
                pass
        bg_path = Path(__file__).parent / "bg.png"
        if bg_path.exists():
            try:
                from PIL import Image
                self._bg_image_original = Image.open(bg_path)
                img = ctk.CTkImage(
                    light_image=self._bg_image_original,
                    dark_image=self._bg_image_original,
                    size=(980, 660)
                )
                bg_lbl = ctk.CTkLabel(self, image=img, text="")
                bg_lbl.place(x=0, y=0, relwidth=1, relheight=1)
                self.bind("<Configure>", self._on_resize)
                self._bg_label = bg_lbl
            except Exception as e:
                logger.warning(f"Background image failed to load: {e}")
        self.attributes("-topmost", True)
        self.after(1000, lambda: self.attributes("-topmost", False))
        self.protocol("WM_DELETE_WINDOW", self._on_close_to_tray)
        self.bind("<Unmap>", self._on_unmap)

    def _on_unmap(self, event) -> None:
        if event.widget is self and self.state() == "iconic":
            logger.info("Window minimized — hiding to system tray.")
            self.withdraw()

    def _on_close_to_tray(self) -> None:
        logger.info("Window close clicked — hiding to system tray.")
        self.withdraw()

    def exit_application(self) -> None:
        logger.info("Shutting down PortalClient application.")
        if self.engine_running and self.on_stop_engine:
            try:
                self.on_stop_engine()
            except Exception:
                pass
        self.engine_running = False
        from core.guard import release as release_mutex
        release_mutex()
        self.destroy()

    def _on_close(self) -> None:
        self.exit_application()

    def _setup_layout(self) -> None:
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self._sidebar = Sidebar(
            self,
            on_nav=self._navigate_to,
            on_logout=self._logout,
            on_diagnostics=lambda: self._navigate_to("diag"),
        )
        self._sidebar.grid(row=0, column=0, sticky="nsew")
        self._sidebar.grid_remove()
        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.grid(row=0, column=1, sticky="nsew", padx=16, pady=16)
        self._content.grid_rowconfigure(0, weight=1)
        self._content.grid_columnconfigure(0, weight=1)
        self._status_bar = ctk.CTkLabel(
            self._content,
            text="",
            font=ctk.CTkFont(family="Segoe UI Variable", size=11),
            text_color=_COLORS["muted"],
            anchor="w",
            height=20
        )
        self._status_bar.grid(row=1, column=0, sticky="ew", pady=(4, 0))

    def _start(self) -> None:
        if safe_mode.is_active():
            logger.warning("Safe Mode active — opening Diagnostics Center.")
            self._show_safe_mode_ui()
        else:
            self._init_session()

    def _show_safe_mode_ui(self) -> None:
        self._sidebar.grid(row=0, column=0, sticky="nsew")
        self._sidebar.show_logged_out()
        self._sidebar.show_safe_mode_indicator()
        self._show_auth_view()
        self._navigate_to("diag")

    def _init_session(self) -> None:
        def _check():
            try:
                cached = self.handler.load_cached_credentials()
                if cached:
                    auth_type = cached.get("type", "userpass")
                    if auth_type == "userpass":
                        username = cached.get("key_or_user", "")
                        password = cached.get("password", "")
                        if username and password:
                            user_data = self.handler.login_username_password(
                                username, password, remember=False
                            )
                            result = {
                                "success": True,
                                "token": self.handler.session_token,
                                "user_data": user_data
                            }
                            self.after(0, lambda: self._on_login_success(result))
                            return
            except Exception as e:
                logger.debug(f"Cached credential check failed: {e}")

            # Seamless local direct entry without password/registration prompt
            try:
                result = self.handler.get_or_create_local_session()
                self.after(0, lambda: self._on_login_success(result))
            except Exception as e:
                logger.error(f"Failed to establish local session: {e}")
                self.after(0, self._show_auth_view)

        threading.Thread(target=_check, daemon=True, name="SessionInitThread").start()

    def _show_auth_view(self) -> None:
        if self._current_tab:
            curr_view = self._views.get(self._current_tab)
            if curr_view:
                curr_view.grid_remove()
            self._current_tab = ""
        if "auth" not in self._views:
            view = AuthView(
                self._content,
                handler=self.handler,
                on_login_success=self._on_login_success,
            )
            self._views["auth"] = view
        else:
            view = self._views["auth"]
        view.grid(row=0, column=0, sticky="nsew")

    def _on_login_success(self, result: dict) -> None:
        self.user_data = result.get("user_data", {})
        self.logged_in = True
        self.is_authenticated = True
        role = self.user_data.get("role", "user")
        self.is_admin = role in ["admin", "moderator"]
        token = result.get("token", "") or self.handler.session_token
        if token:
            from services.quota_service import QuotaService
            self._credit_service = QuotaService(config.AUTH_SERVER_URL, token)
            threading.Thread(
                target=self._refresh_credits_background,
                daemon=True
            ).start()
        self._sidebar.grid(row=0, column=0, sticky="nsew")
        self._sidebar.show_logged_in(self.user_data, is_admin=self.is_admin)
        if self.on_authorized:
            try:
                self.on_authorized()
            except Exception as e:
                logger.error(f"on_authorized callback error: {e}")
        self._navigate_to("dash")
        self._sidebar.refresh_health_async()
        logger.info(f"Login success: {self.user_data.get('username')} ({role})")

    def _refresh_credits_background(self) -> None:
        try:
            status = self._credit_service.refresh()
            self.user_data["credits"] = status.credits
            self.user_data["credits_unlimited"] = status.credits_unlimited
            self.user_data["lifetime_requests"] = status.lifetime_requests
            self.after(0, lambda: self._sidebar.update_credits_display(status.display_credits))
        except Exception:
            pass

    def _logout(self) -> None:
        self.logged_in = False
        self.is_authenticated = False
        self.user_data = {}
        self.is_admin = False
        self._credit_service = None
        if self.on_logout:
            try:
                self.on_logout()
            except Exception as e:
                logger.error(f"on_logout callback error: {e}")
        if self.handler:
            self.handler.session_token = ""
            self.handler.user_info = {}
        for view in self._views.values():
            try:
                view.destroy()
            except Exception:
                pass
        self._views.clear()
        self._current_tab = ""
        if self.engine_running and self.on_stop_engine:
            try:
                self.on_stop_engine()
            except Exception:
                pass
        self.engine_running = False
        try:
            self.handler.delete_cached_credentials()
        except Exception:
            pass
        self._sidebar.show_logged_out()
        self._sidebar.grid_remove()
        self._show_auth_view()
        logger.info("User logged out.")

    def _navigate_to(self, tab: str) -> None:
        if not self.is_authenticated:
            if safe_mode.is_active() and tab in ("diag", "auth"):
                pass
            elif tab == "auth":
                pass
            else:
                logger.warning(f"Unauthenticated navigation blocked to tab: {tab}")
                return
        if tab == "admin" and not self.is_admin:
            logger.warning("Access denied: non-admin navigation blocked to admin tab")
            return
        if self._current_tab == tab:
            return
        if self._current_tab:
            curr_view = self._views.get(self._current_tab)
            if curr_view:
                curr_view.grid_remove()
        if tab != "auth" and "auth" in self._views:
            self._views["auth"].grid_remove()
        self._current_tab = tab
        self._sidebar.set_active_tab(tab)
        self._set_status("")
        view = self._get_or_create_view(tab)
        if view:
            view.grid(row=0, column=0, sticky="nsew")
            if hasattr(view, "on_show"):
                try:
                    view.on_show()
                except Exception as e:
                    logger.error(f"Error calling on_show for {tab}: {e}")

    def _get_or_create_view(self, tab: str) -> Optional[ctk.CTkFrame]:
        if not self.is_authenticated:
            if safe_mode.is_active() and tab == "diag":
                pass
            elif tab == "auth":
                pass
            else:
                logger.warning(f"Unauthenticated attempt to create/access view: {tab}")
                return None
        if tab == "admin" and not self.is_admin:
            logger.warning(f"Non-admin attempt to create/access view: {tab}")
            return None
        if tab in self._views:
            return self._views[tab]
        view_factories = {
            "dash":  self._make_dashboard_view,
            "sub":   self._make_account_view,
            "pref":  self._make_preferences_view,
            "notes": self._make_release_notes_view,
            "diag":  self._make_diagnostics_view,
            "admin": self._make_admin_view,
        }
        factory = view_factories.get(tab)
        if factory:
            view = factory()
            self._views[tab] = view
            return view
        return None

    def _clear_content(self) -> None:
        pass

    def _make_dashboard_view(self) -> ctk.CTkFrame:
        return DashboardView(
            self._content,
            handler=self.handler,
            user_data=self.user_data,
            on_start_engine=self._start_engine,
            on_stop_engine=self._stop_engine,
            on_select_region=self._select_screen_region,
            engine_running=self.engine_running,
        )

    def _make_account_view(self) -> ctk.CTkFrame:
        return AccountView(
            self._content,
            handler=self.handler,
            user_data=self.user_data,
            on_start_engine=self._start_engine,
            on_select_region=self._select_screen_region,
        )

    def _make_preferences_view(self) -> ctk.CTkFrame:
        return PreferencesView(
            self._content,
            on_shortcut_changed=self.on_shortcut_changed,
            on_select_region=self._select_screen_region,
        )

    def _make_release_notes_view(self) -> ctk.CTkFrame:
        return ReleaseNotesView(self._content, handler=self.handler)

    def _make_diagnostics_view(self) -> ctk.CTkFrame:
        token = getattr(self.handler, "session_token", "")
        return DiagnosticsView(
            self._content,
            auth_handler=self.handler,
            session_token=token,
        )

    def _make_admin_view(self) -> ctk.CTkFrame:
        if not self.is_admin:
            placeholder = ctk.CTkFrame(self._content, fg_color="transparent")
            ctk.CTkLabel(
                placeholder,
                text="Access Denied",
                text_color="#EF4444",
                font=ctk.CTkFont(size=18, weight="bold")
            ).pack(pady=40)
            return placeholder
        return AdminView(
            self._content,
            handler=self.handler,
            credit_service=self._credit_service,
            user_data=self.user_data,
            on_status=self._set_status,
        )

    def _start_engine(self) -> None:
        if not self.is_authenticated:
            logger.warning("Unauthenticated attempt to start engine blocked.")
            return
        if self.engine_running:
            return
        if safe_mode.is_active():
            self._set_status("Cannot start engine in Safe Mode.")
            return
        self.engine_running = True
        if self.on_start_engine:
            try:
                self.on_start_engine()
            except Exception as e:
                logger.error(f"Engine start error: {e}")
                self.engine_running = False

    def _stop_engine(self) -> None:
        if not self.is_authenticated:
            logger.warning("Unauthenticated attempt to stop engine blocked.")
            return
        if not self.engine_running:
            return
        self.engine_running = False
        if self.on_stop_engine:
            try:
                self.on_stop_engine()
            except Exception as e:
                logger.error(f"Engine stop error: {e}")

    def _select_screen_region(self) -> None:
        if not self.is_authenticated:
            logger.warning("Unauthenticated attempt to select region blocked.")
            return
        from engine.capture import ScreenCaptureManager
        try:
            cap = ScreenCaptureManager(config, parent=self)
            cap.request_screen_selection(parent=self)
        except Exception as e:
            logger.error(f"Region selection error: {e}")

    def _set_status(self, message: str) -> None:
        self._status_bar.configure(text=message)

    def _on_resize(self, event) -> None:
        if event.widget is not self:
            return
        try:
            if hasattr(self, "_bg_label") and hasattr(self, "_bg_image_original"):
                new_size = (self.winfo_width(), self.winfo_height())
                if new_size != self._last_bg_size and new_size[0] > 100 and new_size[1] > 100:
                    self._last_bg_size = new_size
                    new_img = ctk.CTkImage(
                        light_image=self._bg_image_original,
                        dark_image=self._bg_image_original,
                        size=new_size
                    )
                    self._bg_label.configure(image=new_img)
        except Exception:
            pass

    def _on_close(self) -> None:
        self.exit_application()


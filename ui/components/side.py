import threading
import customtkinter as ctk
from typing import Callable, Dict, Optional

from config import config
from services import status_service

class Sidebar(ctk.CTkFrame):
    HEALTH_ITEMS = [
        ("internet",   "Internet"),
        ("server",     "Auth Server"),
        ("database",   "Database"),
        ("visual_system", "Visual System"),
        ("ai_engine",  "AI Engine"),
        ("storage",    "Storage"),
        ("update",     "Updates"),
    ]

    def __init__(
        self,
        parent,
        on_nav: Callable[[str], None],
        on_logout: Callable,
        on_diagnostics: Callable,
        **kwargs
    ):
        super().__init__(
            parent,
            width=220,
            corner_radius=0,
            fg_color="#0A0B10",
            border_width=1,
            border_color="#1A1C28",
            **kwargs
        )
        self.on_nav = on_nav
        self.on_logout = on_logout
        self.on_diagnostics = on_diagnostics
        self._nav_buttons: Dict[str, ctk.CTkButton] = {}
        self._health_indicators: Dict[str, ctk.CTkLabel] = {}
        self._is_admin = False
        self._safe_mode_indicator: Optional[ctk.CTkLabel] = None
        self._build()

    def _build(self) -> None:
        self.grid_rowconfigure(8, weight=1)
        self._header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._header_frame.grid(row=0, column=0, rowspan=2, padx=12, pady=(20, 10), sticky="ew")

        ctk.CTkLabel(
            self._header_frame,
            text="VISUAL ANALYZER",
            font=ctk.CTkFont(family="Segoe UI Variable", size=22, weight="bold"),
            text_color="#6366F1"
        ).pack(pady=(0, 2))
        ctk.CTkLabel(
            self._header_frame,
            text="✦ Client Interface ✦",
            text_color="#6B7280",
            font=ctk.CTkFont(family="Segoe UI Variable", size=10, weight="bold")
        ).pack(pady=(0, 4))
        nav_items = [
            ("dash",  "  Dashboard",         2),
            ("sub",   "  Account & Devices", 3),
            ("pref",  "  Preferences",       4),
            ("notes", "  Release Notes",     5),
            ("diag",  "  Diagnostics",       6),
        ]
        for tab, label, row in nav_items:
            btn = ctk.CTkButton(
                self,
                text=label,
                anchor="w",
                fg_color="transparent",
                text_color="#9CA3AF",
                hover_color="#12141C",
                corner_radius=8,
                height=36,
                command=lambda t=tab: self._on_nav_click(t),
                font=ctk.CTkFont(family="Segoe UI Variable", size=12, weight="bold")
            )
            btn.grid(row=row, column=0, padx=12, pady=2, sticky="ew")
            self._nav_buttons[tab] = btn
        admin_btn = ctk.CTkButton(
            self,
            text="  Admin Portal",
            anchor="w",
            fg_color="transparent",
            text_color="#9CA3AF",
            hover_color="#12141C",
            corner_radius=8,
            height=36,
            command=lambda: self._on_nav_click("admin"),
            font=ctk.CTkFont(family="Segoe UI Variable", size=12, weight="bold")
        )
        self._nav_buttons["admin"] = admin_btn
        self._build_health_panel()
        self._build_client_panel()
        logout_btn = ctk.CTkButton(
            self,
            text="  Log Out",
            anchor="w",
            fg_color="transparent",
            text_color="#EF4444",
            hover_color="#2A1414",
            corner_radius=8,
            height=36,
            command=self.on_logout,
            font=ctk.CTkFont(family="Segoe UI Variable", size=12, weight="bold")
        )
        logout_btn.grid(row=11, column=0, padx=12, pady=(0, 12), sticky="s")
        self._logout_btn = logout_btn
        logout_btn.grid_remove()

    def _build_health_panel(self) -> None:
        health_frame = ctk.CTkFrame(self, fg_color="transparent")
        health_frame.grid(row=9, column=0, padx=12, pady=(10, 2), sticky="ew")
        ctk.CTkLabel(
            health_frame,
            text="SYSTEM STATUS",
            font=ctk.CTkFont(family="Segoe UI Variable", size=10, weight="bold"),
            text_color="#6B7280",
            anchor="w"
        ).pack(fill="x", padx=5, pady=(0, 4))
        health_grid = ctk.CTkFrame(health_frame, fg_color="transparent")
        health_grid.pack(fill="x", padx=5)
        health_grid.grid_columnconfigure(0, weight=1)
        health_grid.grid_columnconfigure(1, weight=1)
        for idx, (key, name) in enumerate(self.HEALTH_ITEMS):
            row = idx // 2
            col = idx % 2
            item = ctk.CTkFrame(health_grid, fg_color="transparent", height=18)
            item.grid(row=row, column=col, sticky="ew", pady=1)
            lbl = ctk.CTkLabel(
                item,
                text=f"🟡 {name}",
                font=ctk.CTkFont(family="Segoe UI Variable", size=9, weight="bold"),
                text_color="#9CA3AF",
                anchor="w"
            )
            lbl.pack(fill="x", side="left")
            self._health_indicators[key] = lbl

    def _build_client_panel(self) -> None:
        client_frame = ctk.CTkFrame(self, fg_color="transparent")
        client_frame.grid(row=10, column=0, padx=12, pady=(5, 5), sticky="ew")
        ctk.CTkLabel(
            client_frame,
            text="CLIENT INFO",
            font=ctk.CTkFont(family="Segoe UI Variable", size=10, weight="bold"),
            text_color="#6B7280",
            anchor="w"
        ).pack(fill="x", padx=5, pady=(0, 3))
        label_style = {
            "font": ctk.CTkFont(family="Segoe UI Variable", size=10),
            "text_color": "#9CA3AF",
            "anchor": "w",
            "height": 15
        }
        self._lbl_version = ctk.CTkLabel(
            client_frame, text=f"Version: {config.CURRENT_VERSION}", **label_style
        )
        self._lbl_version.pack(fill="x", padx=5)
        self._lbl_role = ctk.CTkLabel(
            client_frame, text="Role: —", **label_style
        )
        self._lbl_role.pack(fill="x", padx=5)
        self._lbl_credits = ctk.CTkLabel(
            client_frame, text="Credits: —", **label_style
        )
        self._lbl_credits.pack(fill="x", padx=5)
        self._lbl_session = ctk.CTkLabel(
            client_frame, text="Session: Inactive", **label_style
        )
        self._lbl_session.pack(fill="x", padx=5)

    def show_logged_out(self) -> None:
        for key, btn in self._nav_buttons.items():
            btn.grid_remove()
        self._logout_btn.grid_remove()
        self._lbl_role.configure(text="Role: —")
        self._lbl_credits.configure(text="Credits: —")
        self._lbl_session.configure(text="Session: Inactive")

    def show_logged_in(self, user_data: dict, is_admin: bool = False) -> None:
        self.hide_safe_mode_indicator()
        self._is_admin = is_admin
        for tab in ["dash", "sub", "pref", "notes", "diag"]:
            self._nav_buttons[tab].grid(
                row={"dash": 2, "sub": 3, "pref": 4, "notes": 5, "diag": 6}[tab],
                column=0, padx=12, pady=2, sticky="ew"
            )
        if is_admin:
            self._nav_buttons["admin"].grid(
                row=7, column=0, padx=12, pady=2, sticky="ew"
            )
        else:
            self._nav_buttons["admin"].grid_remove()
        self._logout_btn.grid(row=11, column=0, padx=12, pady=(0, 12), sticky="s")
        role = user_data.get("role", "user").capitalize()
        self._lbl_role.configure(text=f"Role: {role}")
        self._lbl_session.configure(text="Session: Active")

    def update_credits_display(self, credits_display: str) -> None:
        self._lbl_credits.configure(text=f"Credits: {credits_display}")

    def set_active_tab(self, tab_name: str) -> None:
        tab_colors = {
            "dash":  ("#1E1C2E", "#6366F1"),
            "sub":   ("#12251B", "#22C55E"),
            "pref":  ("#1E1C2E", "#6366F1"),
            "notes": ("#1E1C2E", "#9CA3AF"),
            "diag":  ("#1B1A10", "#F59E0B"),
            "admin": ("#2A1621", "#EC4899"),
        }
        for key, btn in self._nav_buttons.items():
            if key == tab_name:
                fg, text = tab_colors.get(key, ("transparent", "#6366F1"))
                btn.configure(fg_color=fg, text_color=text)
            else:
                btn.configure(fg_color="transparent", text_color="#9CA3AF")

    def apply_health_status(self, status: Dict[str, str]) -> None:
        color_map = {
            "green":  ("🟢", "#10B981"),
            "yellow": ("🟡", "#F59E0B"),
            "red":    ("🔴", "#EF4444"),
        }
        for key, indicator_lbl in self._health_indicators.items():
            display_name = dict(self.HEALTH_ITEMS).get(key, key)
            dot, _ = color_map.get(status.get(key, "red"), ("🔴", "#EF4444"))
            indicator_lbl.configure(text=f"{dot} {display_name}")

    def refresh_health_async(self) -> None:
        def _run():
            try:
                status = status_service.check_all()
                self.after(0, lambda: self.apply_health_status(status))
            except Exception:
                pass
        threading.Thread(target=_run, daemon=True).start()

    def show_safe_mode_indicator(self) -> None:
        if self._safe_mode_indicator is None:
            self._safe_mode_indicator = ctk.CTkLabel(
                self._header_frame,
                text="⚠ SAFE MODE ACTIVE",
                font=ctk.CTkFont(family="Segoe UI Variable", size=11, weight="bold"),
                text_color="#F59E0B",
                fg_color="#1F1700",
                corner_radius=6,
                height=30
            )
        self._safe_mode_indicator.pack(fill="x", padx=6, pady=(4, 6))
        if "diag" in self._nav_buttons:
            self._nav_buttons["diag"].grid(row=6, column=0, padx=12, pady=2, sticky="ew")

    def hide_safe_mode_indicator(self) -> None:
        if self._safe_mode_indicator is not None:
            self._safe_mode_indicator.pack_forget()

    def _on_nav_click(self, tab_name: str) -> None:
        self.set_active_tab(tab_name)
        self.on_nav(tab_name)

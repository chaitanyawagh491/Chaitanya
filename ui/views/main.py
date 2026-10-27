import logging
import threading
import customtkinter as ctk
from typing import Callable, Optional, Dict, Any

from config import config
from ui.components.card import create_status_card
import core.safe as safe

logger = logging.getLogger("DashboardView")

_COLORS = {
    "bg":       "#0A0B10",
    "surface":  "#12141C",
    "border":   "#252838",
    "pass":     "#22C55E",
    "fail":     "#EF4444",
    "warn":     "#F59E0B",
    "text":     "#F3F4F6",
    "muted":    "#9CA3AF",
    "accent":   "#6366F1",
    "accent_hover": "#4F46E5",
}

class DashboardView(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        handler,
        user_data: dict,
        on_start_engine: Callable[[], None],
        on_stop_engine: Callable[[], None],
        on_select_region: Callable[[], None],
        engine_running: bool = False,
        **kwargs
    ):
        import time
        start_time = time.time()
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.handler = handler
        self.user_data = user_data
        self.on_start_engine = on_start_engine
        self.on_stop_engine = on_stop_engine
        self.on_select_region = on_select_region
        self.engine_running = engine_running
        self._build()
        self._load_announcements()
        self._update_engine_status_ui()
        duration = int((time.time() - start_time) * 1000)
        logger.info(f"Dashboard build: {duration}ms")

    def _build(self) -> None:
        title_lbl = ctk.CTkLabel(
            self,
            text="Portal Command Center",
            font=ctk.CTkFont(family="Segoe UI Variable", size=24, weight="bold"),
            text_color=_COLORS["text"]
        )
        title_lbl.pack(anchor="w", pady=(10, 2))
        desc_lbl = ctk.CTkLabel(
            self,
            text="Operate the scanning system and monitor endpoint parameters.",
            text_color=_COLORS["muted"],
            font=ctk.CTkFont(family="Segoe UI Variable", size=13)
        )
        desc_lbl.pack(anchor="w", pady=(0, 10))
        self.lbl_announcement = ctk.CTkLabel(
            self,
            text="📢 Loading system announcements...",
            text_color=_COLORS["text"],
            fg_color=_COLORS["surface"],
            corner_radius=8,
            height=32,
            font=ctk.CTkFont(family="Segoe UI Variable", size=12, weight="bold")
        )
        self.lbl_announcement.pack(fill="x", pady=(0, 15))
        self.hero_card = ctk.CTkFrame(
            self,
            fg_color=_COLORS["surface"],
            border_width=1,
            border_color=_COLORS["accent"],
            corner_radius=16,
            height=160
        )
        self.hero_card.pack(fill="x", pady=(0, 15))
        self.hero_card.pack_propagate(False)
        self.hero_card.grid_columnconfigure(0, weight=1)
        self.hero_card.grid_columnconfigure(1, weight=1)
        self.hero_card.grid_rowconfigure(0, weight=1)
        left_ctrl = ctk.CTkFrame(self.hero_card, fg_color="transparent")
        left_ctrl.grid(row=0, column=0, padx=20, pady=15, sticky="nsew")
        ctk.CTkLabel(
            left_ctrl,
            text="SYSTEM CONTROL",
            font=ctk.CTkFont(family="Segoe UI Variable", size=12, weight="bold"),
            text_color=_COLORS["accent"],
            anchor="w"
        ).pack(fill="x", pady=(0, 8))
        self.btn_toggle = ctk.CTkButton(
            left_ctrl,
            text="START SCANNING ENGINE",
            height=40,
            font=ctk.CTkFont(family="Segoe UI Variable", size=13, weight="bold"),
            fg_color=_COLORS["accent"],
            hover_color=_COLORS["accent_hover"],
            text_color="#FFFFFF",
            corner_radius=12,
            command=self._on_toggle_clicked
        )
        self.btn_toggle.pack(fill="x", pady=(0, 10))
        btn_action_row = ctk.CTkFrame(left_ctrl, fg_color="transparent")
        btn_action_row.pack(fill="x")
        self.btn_select_region = ctk.CTkButton(
            btn_action_row,
            text="Change Region",
            height=28,
            fg_color="transparent",
            border_width=1,
            border_color=_COLORS["border"],
            text_color=_COLORS["text"],
            hover_color="#1E1C2E",
            font=ctk.CTkFont(family="Segoe UI Variable", size=11, weight="bold"),
            corner_radius=10,
            command=self.on_select_region
        )
        self.btn_select_region.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.btn_reset_region = ctk.CTkButton(
            btn_action_row,
            text="Reset Region",
            height=28,
            fg_color="transparent",
            border_width=1,
            border_color=_COLORS["fail"],
            text_color=_COLORS["fail"],
            hover_color="#2A1414",
            font=ctk.CTkFont(family="Segoe UI Variable", size=11, weight="bold"),
            corner_radius=10,
            command=self._on_reset_region_clicked
        )
        self.btn_reset_region.pack(side="right", fill="x", expand=True, padx=(4, 0))
        right_status = ctk.CTkFrame(
            self.hero_card,
            fg_color="#0A0B10",
            border_width=1,
            border_color=_COLORS["border"],
            corner_radius=12
        )
        right_status.grid(row=0, column=1, padx=20, pady=15, sticky="nsew")
        right_status.grid_columnconfigure(0, weight=1)
        right_status.grid_columnconfigure(1, weight=1)
        right_status.grid_rowconfigure((0, 1), weight=1)
        self.lbl_stealth_status = ctk.CTkLabel(
            right_status,
            text="🔴 INACTIVE / STANDBY",
            font=ctk.CTkFont(family="Segoe UI Variable", size=13, weight="bold"),
            text_color=_COLORS["fail"],
            anchor="w"
        )
        self.lbl_stealth_status.grid(row=0, column=0, padx=15, pady=(10, 2), sticky="w")
        self.lbl_stealth_region = ctk.CTkLabel(
            right_status,
            text="Region: Not Configured",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=_COLORS["muted"],
            anchor="w"
        )
        self.lbl_stealth_region.grid(row=1, column=0, padx=15, pady=(2, 10), sticky="w")
        self.lbl_stealth_hotkey = ctk.CTkLabel(
            right_status,
            text=f"Hotkey: {config.GLOBAL_SHORTCUT}",
            font=ctk.CTkFont(family="Segoe UI Variable", size=12, weight="bold"),
            text_color=_COLORS["accent"],
            anchor="e"
        )
        self.lbl_stealth_hotkey.grid(row=0, column=1, padx=15, pady=(10, 2), sticky="e")
        self.lbl_stealth_hook = ctk.CTkLabel(
            right_status,
            text="Engine Hook: Offline",
            font=ctk.CTkFont(family="Segoe UI Variable", size=11),
            text_color=_COLORS["muted"],
            anchor="e"
        )
        self.lbl_stealth_hook.grid(row=1, column=1, padx=15, pady=(2, 10), sticky="e")
        grid_container = ctk.CTkFrame(self, fg_color="transparent")
        grid_container.pack(fill="both", expand=True, pady=(0, 10))
        grid_container.grid_rowconfigure((0, 1), weight=1)
        grid_container.grid_columnconfigure((0, 1, 2), weight=1)
        role = self.user_data.get("role", "user").upper()
        credits_val = self.user_data.get("credits", 0)
        unlimited = self.user_data.get("credits_unlimited", False)
        credits_str = "Unlimited" if unlimited else str(credits_val)
        self.card_user = create_status_card(
            grid_container,
            "USER IDENTITY",
            self.user_data.get("username", "—").upper(),
            "Profile session authenticated",
            _COLORS["pass"]
        )
        self.card_user.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")
        self.card_device = create_status_card(
            grid_container,
            "DEVICE LOCK",
            "BOUND" if self.user_data.get("hwid") else "UNBOUND",
            "Hardware fingerprint security",
            _COLORS["pass"] if self.user_data.get("hwid") else _COLORS["warn"]
        )
        self.card_device.grid(row=0, column=1, padx=6, pady=6, sticky="nsew")
        self.card_clearance = create_status_card(
            grid_container,
            "CLEARANCE LEVEL",
            role,
            "System access privilege role",
            _COLORS["accent"]
        )
        self.card_clearance.grid(row=0, column=2, padx=6, pady=6, sticky="nsew")
        self.card_credits = create_status_card(
            grid_container,
            "BALANCE CREDITS",
            credits_str,
            "Remaining AI scanning limits",
            _COLORS["accent"]
        )
        self.card_credits.grid(row=1, column=0, padx=6, pady=6, sticky="nsew")
        self.card_version = create_status_card(
            grid_container,
            "CURRENT VERSION",
            config.CURRENT_VERSION,
            "Active application build",
            _COLORS["accent"]
        )
        self.card_version.grid(row=1, column=1, padx=6, pady=6, sticky="nsew")
        self.card_status = create_status_card(
            grid_container,
            "SYSTEM HEALTH",
            "SAFE MODE" if safe.is_active() else "NOMINAL",
            "Core component diagnostic status",
            _COLORS["warn"] if safe.is_active() else _COLORS["pass"]
        )
        self.card_status.grid(row=1, column=2, padx=6, pady=6, sticky="nsew")
        self._update_region_display()

    def _load_announcements(self) -> None:
        import time
        now = time.time()
        if now - getattr(self, "_last_announcement_time", 0) < 60:
            return
        self._last_announcement_time = now
        def _fetch():
            try:
                ann = self.handler.get_announcements()
                if ann:
                    self.after(0, lambda: self.lbl_announcement.configure(text=f"📢 {ann}"))
            except Exception:
                pass
        threading.Thread(target=_fetch, daemon=True, name="AnnouncementFetchThread").start()

    def _on_toggle_clicked(self) -> None:
        if safe.is_active():
            logger.warning("Engine controls disabled in Safe Mode.")
            return
        if self.engine_running:
            self.engine_running = False
            self.on_stop_engine()
        else:
            self.engine_running = True
            self.on_start_engine()
        self._update_engine_status_ui()

    def _update_engine_status_ui(self) -> None:
        if safe.is_active():
            self.btn_toggle.configure(text="ENGINE DISABLED (SAFE MODE)", state="disabled", fg_color="#374151")
            self.lbl_stealth_status.configure(text="⚠ DISABLED (SAFE MODE)", text_color=_COLORS["warn"])
            self.lbl_stealth_hook.configure(text="Engine Hook: Offline", text_color=_COLORS["muted"])
            return
        if self.engine_running:
            self.btn_toggle.configure(text="STOP SCANNING ENGINE", fg_color=_COLORS["fail"], hover_color="#DC2626")
            self.lbl_stealth_status.configure(text="🟢 ACTIVE / LISTENING", text_color=_COLORS["pass"])
            self.lbl_stealth_hook.configure(text="Engine Hook: Active", text_color=_COLORS["pass"])
            self.hero_card.configure(border_color=_COLORS["pass"])
        else:
            self.btn_toggle.configure(text="START SCANNING ENGINE", fg_color=_COLORS["accent"], hover_color=_COLORS["accent_hover"])
            self.lbl_stealth_status.configure(text="🔴 INACTIVE / STANDBY", text_color=_COLORS["fail"])
            self.lbl_stealth_hook.configure(text="Engine Hook: Offline", text_color=_COLORS["muted"])
            self.hero_card.configure(border_color=_COLORS["accent"])

    def _on_reset_region_clicked(self) -> None:
        config.CROP_BOX = None
        config.save_to_disk()
        self._update_region_display()

    def _update_region_display(self) -> None:
        if config.CROP_BOX:
            box_str = f"{config.CROP_BOX[2] - config.CROP_BOX[0]}x{config.CROP_BOX[3] - config.CROP_BOX[1]}"
            self.lbl_stealth_region.configure(text=f"Region: {box_str} ({config.CROP_BOX[0]},{config.CROP_BOX[1]})")
        else:
            self.lbl_stealth_region.configure(text="Region: Full Screen")

    def on_show(self) -> None:
        if hasattr(self, "card_user"):
            self.card_user.lbl_val.configure(text=self.user_data.get("username", "—").upper())
        if hasattr(self, "card_device"):
            has_hwid = bool(self.user_data.get("hwid"))
            self.card_device.lbl_val.configure(text="BOUND" if has_hwid else "UNBOUND")
            self.card_device.lbl_val.configure(text_color=_COLORS["pass"] if has_hwid else _COLORS["warn"])
        if hasattr(self, "card_clearance"):
            role = self.user_data.get("role", "user").upper()
            self.card_clearance.lbl_val.configure(text=role)
        if hasattr(self, "card_credits"):
            credits_val = self.user_data.get("credits", 0)
            unlimited = self.user_data.get("credits_unlimited", False)
            credits_str = "Unlimited" if unlimited else str(credits_val)
            self.card_credits.lbl_val.configure(text=credits_str)
        if hasattr(self, "card_status"):
            self.card_status.lbl_val.configure(text="SAFE MODE" if safe.is_active() else "NOMINAL")
            self.card_status.lbl_val.configure(text_color=_COLORS["warn"] if safe.is_active() else _COLORS["pass"])
        if self.master and hasattr(self.master, "master") and hasattr(self.master.master, "engine_running"):
            self.engine_running = self.master.master.engine_running
        self._update_engine_status_ui()
        self._update_region_display()
        self._load_announcements()

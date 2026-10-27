import logging
import customtkinter as ctk
from typing import Callable

logger = logging.getLogger("AccountView")

_COLORS = {
    "bg":       "#0A0B10",
    "surface":  "#12141C",
    "border":   "#252838",
    "pass":     "#22C55E",
    "pass_hover": "#16A34A",
    "text":     "#F3F4F6",
    "muted":    "#9CA3AF",
    "accent":   "#6366F1",
}

class AccountView(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        handler,
        user_data: dict,
        on_start_engine: Callable[[], None],
        on_select_region: Callable[[], None],
        **kwargs
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.handler = handler
        self.user_data = user_data
        self.on_start_engine = on_start_engine
        self.on_select_region = on_select_region
        self._build()

    def _build(self) -> None:
        title_lbl = ctk.CTkLabel(
            self,
            text="Account & Devices",
            font=ctk.CTkFont(family="Segoe UI Variable", size=24, weight="bold"),
            text_color=_COLORS["text"]
        )
        title_lbl.pack(anchor="w", pady=(10, 2))
        desc_lbl = ctk.CTkLabel(
            self,
            text="Active subscription profile and account device lock telemetry.",
            text_color=_COLORS["muted"],
            font=ctk.CTkFont(family="Segoe UI Variable", size=13)
        )
        desc_lbl.pack(anchor="w", pady=(0, 15))
        grid_frame = ctk.CTkFrame(
            self,
            fg_color=_COLORS["surface"],
            border_width=1,
            border_color=_COLORS["border"],
            corner_radius=16
        )
        grid_frame.pack(fill="both", expand=True, pady=(0, 15), padx=5)
        grid_frame.grid_columnconfigure(0, weight=0)
        grid_frame.grid_columnconfigure(1, weight=1)
        self._labels = {}
        rows = [
            ("username", "Username Profile",        self.user_data.get("username", "—")),
            ("role", "Account Role / Clearance", self.user_data.get("role", "—").capitalize()),
            ("hwid", "Device Lock Status",      f"Bound ({self.user_data.get('hwid', '')[:20]}...)" if self.user_data.get("hwid") else "Not Bound"),
            ("ip", "Session Network Address", self.user_data.get("ip", "127.0.0.1")),
            ("createdate", "Registration Date",       self.user_data.get("createdate", "—")[:10] if self.user_data.get("createdate") else "—"),
            ("lastlogin", "Last Server Login",       self.user_data.get("lastlogin", "—")[:19] if self.user_data.get("lastlogin") else "—"),
            ("subscription", "Subscription Plan",       self.user_data.get("subscription", "Standard Client")),
        ]
        for idx, (key, label_text, value) in enumerate(rows):
            grid_frame.grid_rowconfigure(idx, weight=1)
            lbl_title = ctk.CTkLabel(
                grid_frame,
                text=label_text,
                font=ctk.CTkFont(family="Segoe UI Variable", size=12, weight="bold"),
                text_color=_COLORS["muted"],
                anchor="w"
            )
            lbl_title.grid(row=idx, column=0, padx=25, pady=8, sticky="w")
            lbl_val = ctk.CTkLabel(
                grid_frame,
                text=value,
                font=ctk.CTkFont(size=12, family="Consolas"),
                text_color=_COLORS["text"],
                anchor="w"
            )
            lbl_val.grid(row=idx, column=1, padx=25, pady=8, sticky="ew")
            self._labels[key] = lbl_val
        row_idx = len(rows)
        grid_frame.grid_rowconfigure(row_idx, weight=1)
        btn_frm = ctk.CTkFrame(grid_frame, fg_color="transparent")
        btn_frm.grid(row=row_idx, column=0, columnspan=2, padx=25, pady=15, sticky="ew")
        btn_launch = ctk.CTkButton(
            btn_frm,
            text="Open Engine",
            fg_color=_COLORS["pass"],
            hover_color=_COLORS["pass_hover"],
            text_color="#FFFFFF",
            height=36,
            font=ctk.CTkFont(family="Segoe UI Variable", weight="bold"),
            corner_radius=12,
            command=self.on_start_engine
        )
        btn_launch.pack(side="left", padx=(0, 10))
        btn_crop = ctk.CTkButton(
            btn_frm,
            text="Select Screen Region",
            fg_color="transparent",
            border_width=1,
            border_color=_COLORS["border"],
            text_color=_COLORS["pass"],
            hover_color="#1E1C2E",
            height=36,
            font=ctk.CTkFont(family="Segoe UI Variable", weight="bold"),
            corner_radius=12,
            command=self.on_select_region
        )
        btn_crop.pack(side="left", padx=0)

    def on_show(self) -> None:
        if hasattr(self, "_labels"):
            if "username" in self._labels:
                self._labels["username"].configure(text=self.user_data.get("username", "—"))
            if "role" in self._labels:
                self._labels["role"].configure(text=self.user_data.get("role", "—").capitalize())
            if "hwid" in self._labels:
                has_hwid = self.user_data.get("hwid")
                self._labels["hwid"].configure(text=f"Bound ({has_hwid[:20]}...)" if has_hwid else "Not Bound")
            if "ip" in self._labels:
                self._labels["ip"].configure(text=self.user_data.get("ip", "127.0.0.1"))
            if "createdate" in self._labels:
                cdate = self.user_data.get("createdate", "—")
                self._labels["createdate"].configure(text=cdate[:10] if cdate else "—")
            if "lastlogin" in self._labels:
                llogin = self.user_data.get("lastlogin", "—")
                self._labels["lastlogin"].configure(text=llogin[:19] if llogin else "—")
            if "subscription" in self._labels:
                self._labels["subscription"].configure(text=self.user_data.get("subscription", "Standard Client"))

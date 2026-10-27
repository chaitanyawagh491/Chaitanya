import customtkinter as ctk

_COLORS = {
    "bg":       "#0A0B10",
    "surface":  "#12141C",
    "border":   "#252838",
    "text":     "#F3F4F6",
    "muted":    "#9CA3AF",
    "accent":   "#6366F1",
}

class ReleaseNotesView(ctk.CTkFrame):
    def __init__(self, parent, handler=None, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.handler = handler
        self._build()

    def _build(self) -> None:
        title_lbl = ctk.CTkLabel(
            self,
            text="Release Notes",
            font=ctk.CTkFont(family="Segoe UI Variable", size=24, weight="bold"),
            text_color=_COLORS["text"]
        )
        title_lbl.pack(anchor="w", pady=(10, 2))
        desc_lbl = ctk.CTkLabel(
            self,
            text="Learn about the latest updates, stability improvements, and security patches.",
            text_color=_COLORS["muted"],
            font=ctk.CTkFont(family="Segoe UI Variable", size=13)
        )
        desc_lbl.pack(anchor="w", pady=(0, 15))
        scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=_COLORS["surface"],
            border_width=1,
            border_color=_COLORS["border"],
            corner_radius=16
        )
        scroll.pack(fill="both", expand=True)
        self._add_release_version(
            scroll,
            version="PORTAL CLIENT V3.0.0 — MODULE INTEGRATION",
            date="June 2026",
            notes=[
                "✦ Architecture optimization for reliability and system compatibility.",
                "✦ Process management features checking and single-instance verification.",
                "✦ Diagnostics integration validating configuration files and libraries.",
                "✦ Automated requirements verification and package checks.",
                "✦ Enhanced profile management with direct local authentication workflows.",
                "✦ Real-time API consumption tracking.",
                "✦ Fault tolerance with clean fallback systems.",
                "✦ Logging features capturing operational status code errors.",
                "✦ Secure local credential configuration storage."
            ],
            is_latest=True
        )
        self._add_release_version(
            scroll,
            version="PORTAL CLIENT V2.0",
            date="May 2026",
            notes=[
                "✦ Modern visual interfaces with dark color layout.",
                "✦ Enhanced speed and processing execution.",
                "✦ Reduced process footprint and resource usage.",
                "✦ Simplified onboarding flow.",
                "✦ Hotkey controls update and coordinate selection features."
            ],
            is_latest=False
        )

    def _add_release_version(
        self,
        parent,
        version: str,
        date: str,
        notes: list,
        is_latest: bool = False
    ) -> None:
        container = ctk.CTkFrame(
            parent,
            fg_color="#0A0B10" if is_latest else "transparent",
            border_width=1 if is_latest else 0,
            border_color=_COLORS["border"] if is_latest else None,
            corner_radius=12
        )
        container.pack(fill="x", padx=16, pady=8)
        inner = ctk.CTkFrame(container, fg_color="transparent")
        inner.pack(padx=20, pady=16, fill="x")
        title_row = ctk.CTkFrame(inner, fg_color="transparent")
        title_row.pack(fill="x", pady=(0, 4))
        if is_latest:
            badge = ctk.CTkLabel(
                title_row,
                text="LATEST",
                font=ctk.CTkFont(family="Segoe UI Variable", size=9, weight="bold"),
                text_color="#FFFFFF",
                fg_color=_COLORS["accent"],
                corner_radius=4,
                width=50,
                height=16
            )
            badge.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(
            title_row,
            text=version,
            font=ctk.CTkFont(family="Segoe UI Variable", size=14, weight="bold"),
            text_color=_COLORS["text"]
        ).pack(side="left")
        ctk.CTkLabel(
            title_row,
            text=date,
            font=ctk.CTkFont(family="Segoe UI Variable", size=11),
            text_color=_COLORS["muted"]
        ).pack(side="right")
        notes_box = ctk.CTkFrame(inner, fg_color="transparent")
        notes_box.pack(fill="x", pady=(6, 0))
        for note in notes:
            lbl = ctk.CTkLabel(
                notes_box,
                text=note,
                font=ctk.CTkFont(family="Segoe UI Variable", size=12),
                text_color=_COLORS["text"] if is_latest else _COLORS["muted"],
                justify="left",
                anchor="w",
                wraplength=600
            )
            lbl.pack(anchor="w", pady=2, fill="x")

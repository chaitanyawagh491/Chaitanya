import customtkinter as ctk

def create_status_card(
    parent,
    title: str,
    value: str,
    subtext: str,
    value_color: str = "#6366F1",
    wraplength: int = 180
) -> ctk.CTkFrame:
    card = ctk.CTkFrame(
        parent,
        fg_color="#12141C",
        border_width=1,
        border_color="#252838",
        corner_radius=12
    )
    card.grid_columnconfigure(0, weight=1)
    title_lbl = ctk.CTkLabel(
        card,
        text=title.upper(),
        font=ctk.CTkFont(family="Segoe UI Variable", size=11, weight="bold"),
        text_color="#9CA3AF",
        anchor="center",
        wraplength=wraplength
    )
    title_lbl.pack(fill="x", padx=15, pady=(15, 2))
    value_lbl = ctk.CTkLabel(
        card,
        text=value,
        font=ctk.CTkFont(family="Segoe UI Variable", size=18, weight="bold"),
        text_color=value_color,
        anchor="center",
        wraplength=wraplength
    )
    value_lbl.pack(fill="x", padx=15, pady=(0, 2))
    sub_lbl = ctk.CTkLabel(
        card,
        text=subtext,
        font=ctk.CTkFont(family="Segoe UI Variable", size=12),
        text_color="#6B7280",
        anchor="center",
        wraplength=wraplength
    )
    sub_lbl.pack(fill="x", padx=15, pady=(0, 15))
    card.lbl_val = value_lbl
    card.lbl_sub = sub_lbl
    return card

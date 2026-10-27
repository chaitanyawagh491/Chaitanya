import logging
import threading
import customtkinter as ctk
from typing import Callable, Optional

logger = logging.getLogger("AuthView")

_COLORS = {
    "bg":       "#0A0B10",
    "surface":  "#12141C",
    "border":   "#252838",
    "accent":   "#6366F1",
    "accent_hover": "#4F46E5",
    "text":     "#F3F4F6",
    "muted":    "#9CA3AF",
    "pass":     "#22C55E",
    "fail":     "#EF4444",
}

class AuthView(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        handler,
        on_login_success: Callable[[dict], None],
        **kwargs
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.handler = handler
        self.on_login_success = on_login_success
        self._build()

    def _build(self) -> None:
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)
        card = ctk.CTkFrame(
            self,
            width=420,
            height=490,
            fg_color=_COLORS["surface"],
            border_width=1,
            border_color=_COLORS["border"],
            corner_radius=16
        )
        card.grid(row=1, column=0, sticky="")
        card.grid_propagate(False)
        self._tabs = ctk.CTkTabview(
            card,
            fg_color="transparent",
            segmented_button_selected_color=_COLORS["accent"],
            segmented_button_selected_hover_color="#818CF8",
            segmented_button_unselected_color="#181B27",
            segmented_button_unselected_hover_color=_COLORS["border"],
            text_color=_COLORS["text"],
            corner_radius=10
        )
        self._tabs.pack(fill="both", expand=True, padx=25, pady=20)
        self._tab_signin = self._tabs.add("Sign In")
        self._tab_signup = self._tabs.add("Create Account")
        self._build_signin_tab()
        self._build_signup_tab()
        self._lbl_status = ctk.CTkLabel(
            card,
            text="",
            text_color=_COLORS["fail"],
            font=ctk.CTkFont(family="Segoe UI Variable", size=12, weight="bold")
        )
        self._lbl_status.pack(side="bottom", fill="x", pady=(0, 10))

    def _build_signin_tab(self) -> None:
        tab = self._tab_signin
        ctk.CTkLabel(
            tab,
            text="Username:",
            font=ctk.CTkFont(family="Segoe UI Variable", weight="bold", size=12),
            text_color=_COLORS["text"]
        ).pack(anchor="w", padx=10, pady=(15, 2))
        self._ent_login_user = ctk.CTkEntry(
            tab,
            height=38,
            placeholder_text="Username ID",
            fg_color=_COLORS["bg"],
            border_color=_COLORS["border"],
            text_color=_COLORS["text"],
            corner_radius=8
        )
        self._ent_login_user.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkLabel(
            tab,
            text="Password:",
            font=ctk.CTkFont(family="Segoe UI Variable", weight="bold", size=12),
            text_color=_COLORS["text"]
        ).pack(anchor="w", padx=10, pady=(2, 2))
        self._ent_login_pass = ctk.CTkEntry(
            tab,
            height=38,
            placeholder_text="Password",
            show="*",
            fg_color=_COLORS["bg"],
            border_color=_COLORS["border"],
            text_color=_COLORS["text"],
            corner_radius=8
        )
        self._ent_login_pass.pack(fill="x", padx=10, pady=(0, 15))
        self._sw_remember = ctk.CTkSwitch(
            tab,
            text="Remember session on this device",
            font=ctk.CTkFont(family="Segoe UI Variable", size=11),
            progress_color=_COLORS["accent"],
            text_color=_COLORS["muted"]
        )
        self._sw_remember.select()
        self._sw_remember.pack(anchor="w", padx=10, pady=5)
        self._btn_login = ctk.CTkButton(
            tab,
            text="Authenticate",
            height=38,
            font=ctk.CTkFont(family="Segoe UI Variable", size=13, weight="bold"),
            fg_color=_COLORS["accent"],
            hover_color=_COLORS["accent_hover"],
            text_color="#FFFFFF",
            corner_radius=18,
            command=self._on_login_clicked
        )
        self._btn_login.pack(fill="x", padx=10, pady=(15, 6))

        btn_local = ctk.CTkButton(
            tab,
            text="Continue as Local User",
            height=34,
            font=ctk.CTkFont(family="Segoe UI Variable", size=12, weight="bold"),
            fg_color="transparent",
            border_width=1,
            border_color=_COLORS["border"],
            hover_color="#181B27",
            text_color=_COLORS["text"],
            corner_radius=16,
            command=self._on_local_clicked
        )
        btn_local.pack(fill="x", padx=10, pady=(0, 5))

        self._ent_login_user.bind("<Return>", lambda e: self._ent_login_pass.focus())
        self._ent_login_pass.bind("<Return>", lambda e: self._on_login_clicked())

    def _on_local_clicked(self) -> None:
        self._set_status("Initializing local session...", "pass")
        def _task():
            try:
                res = self.handler.get_or_create_local_session()
                self.after(0, lambda: self.on_login_success(res))
            except Exception as e:
                self.after(0, lambda: self._set_status(f"Error: {e}", "fail"))
        threading.Thread(target=_task, daemon=True, name="LocalAuthThread").start()

    def _build_signup_tab(self) -> None:
        tab = self._tab_signup
        ctk.CTkLabel(
            tab,
            text="Choose Username:",
            font=ctk.CTkFont(family="Segoe UI Variable", weight="bold", size=12),
            text_color=_COLORS["text"]
        ).pack(anchor="w", padx=10, pady=(8, 2))
        self._ent_reg_user = ctk.CTkEntry(
            tab,
            height=36,
            placeholder_text="Username ID",
            fg_color=_COLORS["bg"],
            border_color=_COLORS["border"],
            text_color=_COLORS["text"],
            corner_radius=8
        )
        self._ent_reg_user.pack(fill="x", padx=10, pady=(0, 8))
        ctk.CTkLabel(
            tab,
            text="Choose Password:",
            font=ctk.CTkFont(family="Segoe UI Variable", weight="bold", size=12),
            text_color=_COLORS["text"]
        ).pack(anchor="w", padx=10, pady=(2, 2))
        self._ent_reg_pass = ctk.CTkEntry(
            tab,
            height=36,
            placeholder_text="Password",
            show="*",
            fg_color=_COLORS["bg"],
            border_color=_COLORS["border"],
            text_color=_COLORS["text"],
            corner_radius=8
        )
        self._ent_reg_pass.pack(fill="x", padx=10, pady=(0, 8))
        ctk.CTkLabel(
            tab,
            text="Invite / Access Key (Required):",
            font=ctk.CTkFont(family="Segoe UI Variable", weight="bold", size=11),
            text_color=_COLORS["muted"]
        ).pack(anchor="w", padx=10, pady=(2, 2))
        self._ent_reg_invite = ctk.CTkEntry(
            tab,
            height=36,
            placeholder_text="Access Code (e.g. PORTAL-XXXX)",
            fg_color=_COLORS["bg"],
            border_color=_COLORS["border"],
            text_color=_COLORS["text"],
            corner_radius=8
        )
        self._ent_reg_invite.pack(fill="x", padx=10, pady=(0, 15))
        self._btn_register = ctk.CTkButton(
            tab,
            text="Create Profile & Register",
            height=42,
            font=ctk.CTkFont(family="Segoe UI Variable", size=13, weight="bold"),
            fg_color=_COLORS["accent"],
            hover_color=_COLORS["accent_hover"],
            text_color="#FFFFFF",
            corner_radius=20,
            command=self._on_register_clicked
        )
        self._btn_register.pack(fill="x", padx=10, pady=(5, 5))
        self._ent_reg_user.bind("<Return>", lambda e: self._ent_reg_pass.focus())
        self._ent_reg_pass.bind("<Return>", lambda e: self._ent_reg_invite.focus())
        self._ent_reg_invite.bind("<Return>", lambda e: self._on_register_clicked())

    def _set_status(self, text: str, is_error: bool = True) -> None:
        color = _COLORS["fail"] if is_error else _COLORS["pass"]
        self._lbl_status.configure(text=text, text_color=color)

    def _on_login_clicked(self) -> None:
        username = self._ent_login_user.get().strip()
        password = self._ent_login_pass.get().strip()
        remember = bool(self._sw_remember.get())
        if not username or not password:
            self._set_status("Username and password are required.")
            return
        self._btn_login.configure(state="disabled", text="Signing in...")
        self._set_status("", False)
        def _login():
            try:
                user_data = self.handler.login_username_password(
                    username, password, remember=remember
                )
                result = {
                    "success": True,
                    "token": self.handler.session_token,
                    "user_data": user_data
                }
                self.after(0, lambda: self.on_login_success(result))
            except Exception as e:
                self.after(0, lambda: [
                    self._set_status(str(e)),
                    self._btn_login.configure(state="normal", text="Authenticate")
                ])
        threading.Thread(target=_login, daemon=True).start()

    def _on_register_clicked(self) -> None:
        username = self._ent_reg_user.get().strip()
        password = self._ent_reg_pass.get().strip()
        invite = self._ent_reg_invite.get().strip()
        if not username or not password or not invite:
            self._set_status("All fields are required for registration.")
            return
        self._btn_register.configure(state="disabled", text="Registering...")
        self._set_status("", False)
        def _register():
            try:
                user_data = self.handler.register_user(
                    username, password, invite_key=invite
                )
                result = {
                    "success": True,
                    "token": self.handler.session_token,
                    "user_data": user_data
                }
                self.after(0, lambda: self.on_login_success(result))
            except Exception as e:
                self.after(0, lambda: [
                    self._set_status(str(e)),
                    self._btn_register.configure(state="normal", text="Create Profile & Register")
                ])
        threading.Thread(target=_register, daemon=True).start()

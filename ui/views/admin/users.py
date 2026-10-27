import logging
import time
import threading
import customtkinter as ctk
from typing import Optional, Dict, Any, Callable

from config import config

logger = logging.getLogger("UsersView")

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
    "pink":     "#EC4899",
    "red":      "#EF4444",
}

class UsersView(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        handler,
        credit_service=None,
        session_token: str = "",
        on_status: Optional[Callable[[str], None]] = None,
        **kwargs
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.handler = handler
        self.credit_service = credit_service
        self.session_token = session_token
        self.on_status = on_status or (lambda msg: None)
        self._user_cache: Dict[str, Dict[str, Any]] = {}
        self._selected_username: Optional[str] = None
        self._search_query: str = ""
        self._sort_key: str = "Username"
        self._user_row_widgets: Dict[str, ctk.CTkFrame] = {}
        self._build()

    def _build(self) -> None:
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self._build_control_bar()
        self._build_user_list()
        self._build_details_panel()

    def _build_control_bar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=0, pady=(0, 8))
        self._ent_search = ctk.CTkEntry(
            bar,
            placeholder_text="🔍 Search users...",
            height=34,
            fg_color="#0A0B10",
            border_color=_COLORS["border"],
            text_color=_COLORS["text"],
            corner_radius=8
        )
        self._ent_search.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._ent_search.bind("<KeyRelease>", lambda e: self._on_search_changed())
        ctk.CTkLabel(
            bar, text="Sort:",
            font=ctk.CTkFont(family="Segoe UI Variable", size=11),
            text_color=_COLORS["muted"]
        ).pack(side="left", padx=(4, 4))
        self._opt_sort = ctk.CTkOptionMenu(
            bar,
            values=["Username", "Role", "Created", "Last Login"],
            fg_color="#0A0B10",
            button_color=_COLORS["pink"],
            button_hover_color="#F43F5E",
            dropdown_fg_color=_COLORS["surface"],
            height=34,
            width=130,
            corner_radius=8,
            command=lambda v: self._on_sort_changed(v)
        )
        self._opt_sort.pack(side="left", padx=(0, 8))
        self._btn_refresh = ctk.CTkButton(
            bar,
            text="Refresh",
            fg_color=_COLORS["pink"],
            hover_color="#F43F5E",
            height=34,
            width=100,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI Variable", weight="bold"),
            command=self._refresh_users
        )
        self._btn_refresh.pack(side="right")

    def _build_user_list(self) -> None:
        list_container = ctk.CTkFrame(self, fg_color="transparent")
        list_container.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        list_container.grid_rowconfigure(1, weight=1)
        list_container.grid_columnconfigure(0, weight=1)
        hdr = ctk.CTkFrame(
            list_container,
            fg_color=_COLORS["surface"],
            height=30,
            corner_radius=6,
            border_width=1,
            border_color=_COLORS["border"]
        )
        hdr.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        hdr.grid_columnconfigure((0, 1, 2, 3), weight=1)
        for col, label in enumerate(["Username", "Role", "Status", "Last Login"]):
            ctk.CTkLabel(
                hdr, text=label,
                font=ctk.CTkFont(family="Segoe UI Variable", weight="bold", size=11),
                text_color=_COLORS["muted"],
                anchor="w"
            ).grid(row=0, column=col, padx=(14 if col == 0 else 5), sticky="ew")
        self._users_scroll = ctk.CTkScrollableFrame(
            list_container, fg_color="transparent"
        )
        self._users_scroll.grid(row=1, column=0, sticky="nsew")
        self._users_scroll.grid_columnconfigure(0, weight=1)
        self._lbl_empty = ctk.CTkLabel(
            self._users_scroll,
            text="No users found. Click Refresh to load.",
            text_color=_COLORS["muted"],
            font=ctk.CTkFont(family="Segoe UI Variable", size=12)
        )

    def _build_details_panel(self) -> None:
        self._details_frame = ctk.CTkScrollableFrame(
            self,
            fg_color=_COLORS["surface"],
            border_width=1,
            border_color=_COLORS["border"],
            corner_radius=16
        )
        self._details_frame.grid(row=1, column=1, sticky="nsew")
        self._details_frame.grid_columnconfigure(0, weight=1)
        self._no_selection_lbl = ctk.CTkLabel(
            self._details_frame,
            text="Select a user to view details.",
            text_color=_COLORS["muted"],
            font=ctk.CTkFont(family="Segoe UI Variable", size=12),
            wraplength=200
        )
        self._no_selection_lbl.grid(row=0, column=0, padx=20, pady=40)
        self._detail_labels: Dict[str, ctk.CTkLabel] = {}
        detail_fields = [
            ("username",          "Username"),
            ("role",              "Role"),
            ("status",            "Status"),
            ("device_lock",       "Device Lock"),
            ("joined",            "Member Since"),
            ("last_login",        "Last Login"),
            ("credits",           "Credits"),
            ("lifetime_requests", "Lifetime Requests"),
        ]
        row_idx = 1
        for key, label in detail_fields:
            ctk.CTkLabel(
                self._details_frame,
                text=label,
                font=ctk.CTkFont(family="Segoe UI Variable", size=11, weight="bold"),
                text_color=_COLORS["muted"],
                anchor="w"
            ).grid(row=row_idx, column=0, padx=20, pady=(8, 0), sticky="w")
            val_lbl = ctk.CTkLabel(
                self._details_frame,
                text="—",
                font=ctk.CTkFont(family="Consolas", size=12),
                text_color=_COLORS["text"],
                anchor="w",
                wraplength=220
            )
            val_lbl.grid(row=row_idx + 1, column=0, padx=20, pady=(0, 2), sticky="w")
            self._detail_labels[key] = val_lbl
            row_idx += 2
        self._build_action_buttons(row_idx)
        self._show_no_selection()

    def _build_action_buttons(self, start_row: int) -> None:
        sep = ctk.CTkFrame(
            self._details_frame, height=1, fg_color=_COLORS["border"]
        )
        sep.grid(row=start_row, column=0, sticky="ew", padx=20, pady=10)
        btn_style = {
            "height": 34,
            "corner_radius": 8,
            "font": ctk.CTkFont(family="Segoe UI Variable", weight="bold", size=12)
        }
        row = start_row + 1
        self._btn_ban = ctk.CTkButton(
            self._details_frame,
            text="Ban User",
            fg_color="transparent",
            border_width=1,
            border_color="#7F1D1D",
            text_color=_COLORS["fail"],
            hover_color="#2A1010",
            command=self._action_ban,
            **btn_style
        )
        self._btn_ban.grid(row=row, column=0, padx=20, pady=4, sticky="ew")
        self._btn_unban = ctk.CTkButton(
            self._details_frame,
            text="Unban User",
            fg_color="transparent",
            border_width=1,
            border_color="#14532D",
            text_color=_COLORS["pass"],
            hover_color="#0A2010",
            command=self._action_unban,
            **btn_style
        )
        self._btn_unban.grid(row=row + 1, column=0, padx=20, pady=4, sticky="ew")
        self._btn_reset_device = ctk.CTkButton(
            self._details_frame,
            text="Reset Device Lock",
            fg_color="transparent",
            border_width=1,
            border_color=_COLORS["border"],
            text_color=_COLORS["warn"],
            hover_color="#1A1208",
            command=self._action_reset_hwid,
            **btn_style
        )
        self._btn_reset_device.grid(row=row + 2, column=0, padx=20, pady=4, sticky="ew")
        self._btn_reset_pass = ctk.CTkButton(
            self._details_frame,
            text="Reset Password",
            fg_color="transparent",
            border_width=1,
            border_color=_COLORS["border"],
            text_color=_COLORS["muted"],
            hover_color="#1A1C28",
            command=self._action_reset_password,
            **btn_style
        )
        self._btn_reset_pass.grid(row=row + 3, column=0, padx=20, pady=4, sticky="ew")
        credits_header = ctk.CTkFrame(
            self._details_frame, height=1, fg_color=_COLORS["border"]
        )
        credits_header.grid(row=row + 4, column=0, sticky="ew", padx=20, pady=(12, 4))
        ctk.CTkLabel(
            self._details_frame,
            text="CREDITS",
            font=ctk.CTkFont(family="Segoe UI Variable", size=10, weight="bold"),
            text_color=_COLORS["muted"]
        ).grid(row=row + 5, column=0, padx=20, sticky="w")
        add_row = ctk.CTkFrame(self._details_frame, fg_color="transparent")
        add_row.grid(row=row + 6, column=0, padx=20, pady=4, sticky="ew")
        add_row.grid_columnconfigure(0, weight=1)
        self._ent_credit_amount = ctk.CTkEntry(
            add_row,
            placeholder_text="Amount",
            height=32,
            fg_color="#0A0B10",
            border_color=_COLORS["border"],
            text_color=_COLORS["text"],
            corner_radius=8
        )
        self._ent_credit_amount.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(
            add_row,
            text="Add",
            fg_color=_COLORS["accent"],
            hover_color="#4F46E5",
            height=32,
            width=56,
            corner_radius=8,
            command=self._action_add_credits,
            font=ctk.CTkFont(weight="bold")
        ).grid(row=0, column=1)
        self._btn_unlimited = ctk.CTkButton(
            self._details_frame,
            text="Set Unlimited Credits",
            fg_color="transparent",
            border_width=1,
            border_color=_COLORS["border"],
            text_color=_COLORS["accent"],
            hover_color="#1A1C28",
            command=self._action_toggle_unlimited,
            **btn_style
        )
        self._btn_unlimited.grid(row=row + 7, column=0, padx=20, pady=4, sticky="ew")
        delete_sep = ctk.CTkFrame(
            self._details_frame, height=1, fg_color=_COLORS["border"]
        )
        delete_sep.grid(row=row + 8, column=0, sticky="ew", padx=20, pady=(12, 4))
        self._btn_delete = ctk.CTkButton(
            self._details_frame,
            text="Delete Account",
            fg_color="#3A0808",
            hover_color="#500A0A",
            text_color=_COLORS["fail"],
            command=self._action_delete,
            **btn_style
        )
        self._btn_delete.grid(row=row + 9, column=0, padx=20, pady=(4, 16), sticky="ew")
        self._action_row_start = row
        self._all_action_buttons = [
            self._btn_ban, self._btn_unban, self._btn_reset_device,
            self._btn_reset_pass, self._btn_unlimited, self._btn_delete
        ]

    def load_users(self, users: list) -> None:
        self._selected_username = None
        self._user_cache = {}
        for user in users:
            username = user.get("username", "").strip()
            if username:
                self._user_cache[username] = user
        self._render_user_rows()
        self._show_no_selection()

    def _refresh_users(self) -> None:
        toplevel = self.winfo_toplevel()
        if not getattr(toplevel, "is_authenticated", False) or not getattr(toplevel, "is_admin", False):
            logger.warning("Unauthorized user refresh attempt blocked in UsersView.")
            return
        self._btn_refresh.configure(text="Loading...", state="disabled")
        self.on_status("Loading user directory...")
        def _fetch():
            start_time = time.time()
            try:
                result = self.handler.admin_get_users()
                duration = int((time.time() - start_time) * 1000)
                logger.info(f"User fetch: {duration}ms")
                if isinstance(result, list):
                    self.after(0, lambda: self._on_users_loaded(result))
                else:
                    self.after(0, lambda: self._on_load_error(str(result)))
            except Exception as e:
                err = str(e)
                self.after(0, lambda: self._on_load_error(err))
        threading.Thread(target=_fetch, daemon=True).start()

    def _on_users_loaded(self, users: list) -> None:
        self._btn_refresh.configure(text="Refresh", state="normal")
        self.load_users(users)
        count = len(self._user_cache)
        self.on_status(f"Loaded {count} user{'s' if count != 1 else ''}.")

    def _on_load_error(self, error: str) -> None:
        self._btn_refresh.configure(text="Refresh", state="normal")
        self.on_status(f"Failed to load users: {error}")

    def _render_user_rows(self) -> None:
        for widget in self._users_scroll.winfo_children():
            widget.destroy()
        self._user_row_widgets.clear()
        query = self._search_query.lower()
        filtered = [
            u for u in self._user_cache.values()
            if not query or query in u.get("username", "").lower()
        ]
        sort_map = {
            "Username":   lambda u: u.get("username", "").lower(),
            "Role":       lambda u: u.get("role", ""),
            "Created":    lambda u: u.get("created_at", ""),
            "Last Login": lambda u: u.get("last_login", ""),
        }
        key_fn = sort_map.get(self._sort_key, sort_map["Username"])
        filtered.sort(key=key_fn)
        if not filtered:
            self._lbl_empty = ctk.CTkLabel(
                self._users_scroll,
                text="No users found.",
                text_color=_COLORS["muted"],
                font=ctk.CTkFont(family="Segoe UI Variable", size=12)
            )
            self._lbl_empty.grid(row=0, column=0, pady=20)
            return
        def _render_batch(start_idx: int):
            if not self.winfo_exists():
                return
            batch_size = 5
            end_idx = min(start_idx + batch_size, len(filtered))
            for idx in range(start_idx, end_idx):
                self._create_user_row(idx, filtered[idx])
            if end_idx < len(filtered):
                self.after(5, lambda: _render_batch(end_idx))
            else:
                if self._selected_username and self._selected_username in self._user_cache:
                    self._highlight_row(self._selected_username)
                    self._populate_details(self._user_cache[self._selected_username])
        _render_batch(0)

    def _create_user_row(self, idx: int, user: dict) -> None:
        username = user.get("username", "")
        role = user.get("role", "user").capitalize()
        is_banned = user.get("is_banned", 0)
        last_login = user.get("last_login", "N/A") or "Never"
        is_owner = user.get("is_owner", False)
        if is_banned:
            status_text = "BANNED"
            status_color = _COLORS["fail"]
        elif not user.get("hwid"):
            status_text = "NO LOCK"
            status_color = _COLORS["warn"]
        else:
            status_text = "ACTIVE"
            status_color = _COLORS["pass"]
        row = ctk.CTkFrame(
            self._users_scroll,
            fg_color="#0D0E15",
            border_width=1,
            border_color="#1A1C28",
            corner_radius=8,
            height=44
        )
        row.grid(row=idx, column=0, sticky="ew", padx=4, pady=2)
        row.grid_columnconfigure((0, 1, 2, 3), weight=1)
        display_name = f"⭐ {username}" if is_owner else username
        role_display = f"{role} (Owner)" if is_owner else role
        name_lbl = ctk.CTkLabel(
            row, text=display_name,
            font=ctk.CTkFont(family="Segoe UI Variable", size=12, weight="bold"),
            text_color=_COLORS["pink"] if is_owner else _COLORS["text"],
            anchor="w"
        )
        name_lbl.grid(row=0, column=0, padx=(12, 0), pady=10, sticky="ew")
        ctk.CTkLabel(
            row, text=role_display,
            font=ctk.CTkFont(family="Segoe UI Variable", size=11),
            text_color=_COLORS["muted"],
            anchor="w"
        ).grid(row=0, column=1, padx=5, pady=10, sticky="ew")
        ctk.CTkLabel(
            row, text=status_text,
            font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
            text_color=status_color,
            anchor="w"
        ).grid(row=0, column=2, padx=5, pady=10, sticky="ew")
        login_short = last_login[:10] if len(last_login) > 10 else last_login
        ctk.CTkLabel(
            row, text=login_short,
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=_COLORS["muted"],
            anchor="w"
        ).grid(row=0, column=3, padx=5, pady=10, sticky="ew")
        def _on_click(event, uname=username):
            self._select_user(uname)
        row.bind("<Button-1>", _on_click)
        name_lbl.bind("<Button-1>", _on_click)
        def _hover_enter(e, r=row, u=username):
            if u != self._selected_username:
                r.configure(fg_color="#131425")
        def _hover_leave(e, r=row, u=username):
            if u != self._selected_username:
                r.configure(fg_color="#0D0E15")
        row.bind("<Enter>", _hover_enter)
        row.bind("<Leave>", _hover_leave)
        self._user_row_widgets[username] = row

    def _select_user(self, username: str) -> None:
        if username not in self._user_cache:
            return
        if self._selected_username and self._selected_username in self._user_row_widgets:
            self._user_row_widgets[self._selected_username].configure(fg_color="#0D0E15")
        self._selected_username = username
        self._highlight_row(username)
        self._populate_details(self._user_cache[username])

    def _highlight_row(self, username: str) -> None:
        if username in self._user_row_widgets:
            self._user_row_widgets[username].configure(fg_color="#1A1B2E")

    def _get_selected_user(self) -> Optional[dict]:
        if not self._selected_username:
            return None
        return self._user_cache.get(self._selected_username)

    def _populate_details(self, user: dict) -> None:
        self._no_selection_lbl.grid_remove()
        for widget in self._all_action_buttons:
            widget.configure(state="normal")
        username = user.get("username", "—")
        role = user.get("role", "user").capitalize()
        is_banned = user.get("is_banned", 0)
        hwid = user.get("hwid")
        is_owner = user.get("is_owner", False)
        if is_banned:
            status_str = "🔴 Banned"
        elif not hwid:
            status_str = "🟡 Active (No Device Lock)"
        else:
            status_str = "🟢 Active"
        device_str = f"Bound ({hwid[:12]}...)" if hwid else "Not bound"
        credits_val = user.get("credits")
        credits_unlimited = user.get("credits_unlimited", False)
        if credits_unlimited:
            credits_str = "Unlimited"
        elif credits_val is not None:
            credits_str = str(credits_val)
        else:
            credits_str = "—"
        field_values = {
            "username":          f"{username}{'  ⭐ Owner' if is_owner else ''}",
            "role":              role,
            "status":            status_str,
            "device_lock":       device_str,
            "joined":            user.get("created_at", "—")[:10] if user.get("created_at") else "—",
            "last_login":        user.get("last_login", "—") or "Never",
            "credits":           credits_str,
            "lifetime_requests": str(user.get("lifetime_requests", 0) or 0),
        }
        for key, value in field_values.items():
            if key in self._detail_labels:
                self._detail_labels[key].configure(text=value)
        if is_banned:
            self._btn_ban.configure(state="disabled")
            self._btn_unban.configure(state="normal")
        else:
            self._btn_ban.configure(state="normal")
            self._btn_unban.configure(state="disabled")
        if credits_unlimited:
            self._btn_unlimited.configure(text="Remove Unlimited Credits")
        else:
            self._btn_unlimited.configure(text="Set Unlimited Credits")
        if is_owner:
            for btn in [self._btn_ban, self._btn_unban, self._btn_delete]:
                btn.configure(state="disabled")

    def _show_no_selection(self) -> None:
        self._selected_username = None
        self._no_selection_lbl.grid(row=0, column=0, padx=20, pady=40)
        for key, lbl in self._detail_labels.items():
            lbl.configure(text="—")
        for btn in self._all_action_buttons:
            btn.configure(state="disabled")

    def _on_search_changed(self) -> None:
        self._search_query = self._ent_search.get()
        self._render_user_rows()

    def _on_sort_changed(self, value: str) -> None:
        self._sort_key = value
        self._render_user_rows()

    def _get_confirmed_target(self, action_name: str) -> Optional[str]:
        toplevel = self.winfo_toplevel()
        if not getattr(toplevel, "is_authenticated", False) or not getattr(toplevel, "is_admin", False):
            logger.warning(f"Unauthorized admin action '{action_name}' attempt blocked in UsersView.")
            return None
        username = self._selected_username
        if not username:
            self.on_status("No user selected.")
            return None
        if username not in self._user_cache:
            self.on_status(f"User '{username}' not found in cache. Please refresh.")
            return None
        return username

    def _run_action_async(self, action_fn, success_msg: str) -> None:
        self.on_status("Processing...")
        def _run():
            try:
                msg = action_fn()
                display_msg = msg if msg else success_msg
                self.after(0, lambda: self.on_status(f"✓ {display_msg}"))
                self.after(0, self._refresh_users)
            except RuntimeError as e:
                err = str(e)
                self.after(0, lambda: self.on_status(f"✗ {err}"))
            except Exception as e:
                err = str(e)
                self.after(0, lambda: self.on_status(f"Error: {err}"))
        threading.Thread(target=_run, daemon=True).start()

    def _action_ban(self) -> None:
        target = self._get_confirmed_target("ban")
        if not target:
            return
        self._run_action_async(
            lambda: self.handler.admin_ban_user(target, banned=True),
            f"User '{target}' banned."
        )

    def _action_unban(self) -> None:
        target = self._get_confirmed_target("unban")
        if not target:
            return
        self._run_action_async(
            lambda: self.handler.admin_ban_user(target, banned=False),
            f"User '{target}' unbanned."
        )

    def _action_reset_hwid(self) -> None:
        target = self._get_confirmed_target("reset_hwid")
        if not target:
            return
        self._run_action_async(
            lambda: self.handler.admin_reset_hwid(target),
            f"Device lock cleared for '{target}'."
        )

    def _action_reset_password(self) -> None:
        target = self._get_confirmed_target("reset_pass")
        if not target:
            return
        self._show_reset_password_dialog(target)

    def _action_delete(self) -> None:
        target = self._get_confirmed_target("delete")
        if not target:
            return
        self._show_confirm_delete_dialog(target)

    def _action_add_credits(self) -> None:
        if not self.credit_service:
            self.on_status("Credit service not available.")
            return
        target = self._get_confirmed_target("add_credits")
        if not target:
            return
        amount_str = self._ent_credit_amount.get().strip()
        if not amount_str.isdigit() or int(amount_str) <= 0:
            self.on_status("Enter a valid credit amount (positive integer).")
            return
        amount = int(amount_str)
        def _add():
            try:
                msg = self.credit_service.admin_add_credits(target, amount)
                self.after(0, lambda: self.on_status(f"✓ {msg}"))
                self.after(0, self._refresh_users)
            except Exception as e:
                err = str(e)
                self.after(0, lambda: self.on_status(f"Credits error: {err}"))
        threading.Thread(target=_add, daemon=True).start()
        self._ent_credit_amount.delete(0, "end")

    def _action_toggle_unlimited(self) -> None:
        if not self.credit_service:
            self.on_status("Credit service not available.")
            return
        target = self._get_confirmed_target("unlimited_credits")
        if not target:
            return
        user = self._user_cache.get(target)
        if not user:
            return
        current_unlimited = bool(user.get("credits_unlimited", False))
        new_unlimited = not current_unlimited
        def _toggle():
            try:
                msg = self.credit_service.admin_set_unlimited(target, new_unlimited)
                state = "enabled" if new_unlimited else "disabled"
                self.after(0, lambda: self.on_status(f"✓ Unlimited credits {state} for '{target}'."))
                self.after(0, self._refresh_users)
            except Exception as e:
                err = str(e)
                self.after(0, lambda: self.on_status(f"Credits error: {err}"))
        threading.Thread(target=_toggle, daemon=True).start()

    def _show_confirm_delete_dialog(self, target_username: str) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirm Delete")
        dialog.geometry("380x200")
        dialog.resizable(False, False)
        dialog.configure(fg_color=_COLORS["bg"])
        dialog.attributes("-topmost", True)
        dialog.grab_set()
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 380) // 2
        y = self.winfo_y() + (self.winfo_height() - 200) // 2
        dialog.geometry(f"380x200+{x}+{y}")
        ctk.CTkLabel(
            dialog,
            text=f"Permanently delete '{target_username}'?",
            font=ctk.CTkFont(family="Segoe UI Variable", size=13, weight="bold"),
            text_color=_COLORS["text"],
            wraplength=330
        ).pack(pady=(28, 6))
        ctk.CTkLabel(
            dialog,
            text="This action cannot be undone.",
            font=ctk.CTkFont(family="Segoe UI Variable", size=12),
            text_color=_COLORS["fail"]
        ).pack(pady=(0, 20))
        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(fill="x", padx=30)
        def _confirm():
            dialog.destroy()
            self._run_action_async(
                lambda: self.handler.admin_delete_user(target_username),
                f"User '{target_username}' deleted."
            )
        ctk.CTkButton(
            btn_row, text="Confirm Delete",
            fg_color="#7F1D1D", hover_color="#991B1B",
            text_color=_COLORS["fail"], height=36, corner_radius=10,
            command=_confirm
        ).pack(side="left", expand=True, padx=(0, 8))
        ctk.CTkButton(
            btn_row, text="Cancel",
            fg_color="transparent", border_width=1, border_color=_COLORS["border"],
            text_color=_COLORS["muted"], hover_color="#1F2937",
            height=36, corner_radius=10, command=dialog.destroy
        ).pack(side="right", expand=True, padx=(8, 0))

    def _show_reset_password_dialog(self, target_username: str) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Reset Password")
        dialog.geometry("380x220")
        dialog.resizable(False, False)
        dialog.configure(fg_color=_COLORS["bg"])
        dialog.attributes("-topmost", True)
        dialog.grab_set()
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 380) // 2
        y = self.winfo_y() + (self.winfo_height() - 220) // 2
        dialog.geometry(f"380x220+{x}+{y}")
        ctk.CTkLabel(
            dialog,
            text=f"Reset password for '{target_username}'",
            font=ctk.CTkFont(family="Segoe UI Variable", size=13, weight="bold"),
            text_color=_COLORS["text"]
        ).pack(pady=(24, 12))
        ent = ctk.CTkEntry(
            dialog,
            placeholder_text="New password",
            height=38,
            fg_color="#0D0E15",
            border_color=_COLORS["border"],
            show="*",
            corner_radius=8
        )
        ent.pack(fill="x", padx=30, pady=(0, 16))
        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(fill="x", padx=30)
        def _confirm():
            password = ent.get().strip()
            if not password:
                return
            dialog.destroy()
            self._run_action_async(
                lambda: self.handler.admin_reset_password(target_username, password),
                f"Password reset for '{target_username}'."
            )
        ctk.CTkButton(
            btn_row, text="Reset Password",
            fg_color=_COLORS["accent"], hover_color="#4F46E5",
            height=36, corner_radius=10, command=_confirm
        ).pack(side="left", expand=True, padx=(0, 8))
        ctk.CTkButton(
            btn_row, text="Cancel",
            fg_color="transparent", border_width=1, border_color=_COLORS["border"],
            text_color=_COLORS["muted"], hover_color="#1F2937",
            height=36, corner_radius=10, command=dialog.destroy
        ).pack(side="right", expand=True, padx=(8, 0))

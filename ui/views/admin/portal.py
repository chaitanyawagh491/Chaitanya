import logging
import threading
import tkinter.messagebox as messagebox
import customtkinter as ctk
from datetime import datetime
from typing import Callable, Optional

from config import config
from ui.views.admin.users import UsersView

logger = logging.getLogger("AdminView")

_COLORS = {
    "bg":       "#0A0B10",
    "surface":  "#12141C",
    "border":   "#252838",
    "pass":     "#22C55E",
    "fail":     "#EF4444",
    "text":     "#F3F4F6",
    "muted":    "#9CA3AF",
    "accent":   "#6366F1",
    "accent_hover": "#4F46E5",
    "pink":     "#EC4899",
    "pink_hover": "#F43F5E",
}

class AdminView(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        handler,
        credit_service=None,
        user_data: Optional[dict] = None,
        on_status: Optional[Callable[[str], None]] = None,
        **kwargs
    ):
        import time
        start_time = time.time()
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.handler = handler
        self.credit_service = credit_service
        self.user_data = user_data or {}
        self.on_status = on_status or (lambda msg: None)
        self._users_built = False
        self._invites_built = False
        self._config_built = False
        self._logs_built = False
        self._build()
        duration = int((time.time() - start_time) * 1000)
        logger.info(f"Admin load: {duration}ms")

    def _build(self) -> None:
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._tabs = ctk.CTkTabview(
            self,
            fg_color="transparent",
            segmented_button_selected_color=_COLORS["pink"],
            segmented_button_selected_hover_color=_COLORS["pink_hover"],
            segmented_button_unselected_color="#181B27",
            segmented_button_unselected_hover_color=_COLORS["border"],
            text_color=_COLORS["text"],
            corner_radius=12
        )
        self._tabs.grid(row=0, column=0, sticky="nsew")
        self._tab_users = self._tabs.add("Users")
        self._tab_invites = self._tabs.add("Access Codes")
        self._tab_config = self._tabs.add("System Config")
        self._tab_logs = self._tabs.add("Logs")
        self._tabs.configure(command=self._on_tab_changed)

    def _on_tab_changed(self) -> None:
        self._refresh_active_tab()

    def _refresh_active_tab(self) -> None:
        current_tab = self._tabs.get()
        self.on_status(f"Opening {current_tab} panel...")
        if current_tab == "Users":
            if not self._users_built:
                self._build_users_tab()
                self._users_built = True
            self.users_view._refresh_users()
        elif current_tab == "Access Codes":
            if not self._invites_built:
                self._build_invites_tab()
                self._invites_built = True
            self._refresh_invites()
        elif current_tab == "System Config":
            if not self._config_built:
                self._build_config_tab()
                self._config_built = True
        elif current_tab == "Logs":
            if not self._logs_built:
                self._build_logs_tab()
                self._logs_built = True
            self._refresh_logs()

    def on_show(self) -> None:
        self._refresh_active_tab()

    def _build_users_tab(self) -> None:
        self._tab_users.grid_rowconfigure(0, weight=1)
        self._tab_users.grid_columnconfigure(0, weight=1)
        self.users_view = UsersView(
            self._tab_users,
            handler=self.handler,
            credit_service=self.credit_service,
            session_token=getattr(self.handler, "session_token", ""),
            on_status=self.on_status
        )
        self.users_view.grid(row=0, column=0, sticky="nsew")

    def _build_invites_tab(self) -> None:
        self._tab_invites.grid_columnconfigure(0, weight=3)
        self._tab_invites.grid_columnconfigure(1, weight=1)
        self._tab_invites.grid_rowconfigure(0, weight=1)
        self._invites_scroll = ctk.CTkScrollableFrame(self._tab_invites, fg_color="transparent")
        self._invites_scroll.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=4)
        self._invites_scroll.grid_columnconfigure(0, weight=1)
        ctrl = ctk.CTkFrame(
            self._tab_invites,
            fg_color=_COLORS["surface"],
            border_width=1,
            border_color=_COLORS["border"],
            corner_radius=12
        )
        ctrl.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=4)
        ctrl.pack_propagate(False)
        ctk.CTkLabel(
            ctrl,
            text="ACCESS CODE CONTROLS",
            font=ctk.CTkFont(family="Segoe UI Variable", weight="bold", size=12),
            text_color=_COLORS["pink"],
            anchor="w"
        ).pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(
            ctrl,
            text="Generate invite keys to allow users to register an account. Self-registration is otherwise blocked.",
            font=ctk.CTkFont(family="Segoe UI Variable", size=11),
            text_color=_COLORS["muted"],
            wraplength=180,
            justify="left"
        ).pack(padx=16, pady=4)
        self._btn_gen_invite = ctk.CTkButton(
            ctrl,
            text="Generate Access Key",
            fg_color=_COLORS["pink"],
            hover_color=_COLORS["pink_hover"],
            text_color="#FFFFFF",
            corner_radius=10,
            height=38,
            font=ctk.CTkFont(family="Segoe UI Variable", weight="bold"),
            command=self._generate_invite_clicked
        )
        self._btn_gen_invite.pack(fill="x", padx=16, pady=24)

    def _refresh_invites(self) -> None:
        self.on_status("Fetching access codes...")
        def _fetch():
            try:
                keys = self.handler.admin_get_invites()
                self.after(0, lambda: self._render_invites(keys))
            except Exception as e:
                err = str(e)
                self.after(0, lambda: self.on_status(f"Failed to fetch invites: {err}"))
        threading.Thread(target=_fetch, daemon=True).start()

    def _render_invites(self, keys: list) -> None:
        for widget in self._invites_scroll.winfo_children():
            widget.destroy()
        if not keys:
            ctk.CTkLabel(
                self._invites_scroll,
                text="No invite keys generated.",
                text_color=_COLORS["muted"]
            ).grid(row=0, column=0, pady=20)
            return
        for idx, item in enumerate(keys):
            key = item.get("key", "")
            is_used = item.get("is_used", 0) == 1
            used_by = item.get("used_by", "")
            date_str = item.get("created_at", "")[:10]
            row = ctk.CTkFrame(
                self._invites_scroll,
                fg_color="#0D0E15",
                border_width=1,
                border_color="#1A1C28",
                corner_radius=8,
                height=42
            )
            row.grid(row=idx, column=0, sticky="ew", padx=4, pady=2)
            row.grid_columnconfigure(0, weight=1)
            lbl_key = ctk.CTkLabel(
                row,
                text=key,
                font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
                text_color=_COLORS["text"] if not is_used else _COLORS["muted"]
            )
            lbl_key.pack(side="left", padx=12, pady=8)
            status_text = f"Used by {used_by}" if is_used else "Available"
            status_color = _COLORS["muted"] if is_used else _COLORS["pass"]
            lbl_status = ctk.CTkLabel(
                row,
                text=status_text,
                font=ctk.CTkFont(family="Segoe UI Variable", size=11, weight="bold"),
                text_color=status_color
            )
            lbl_status.pack(side="left", padx=20)
            ctk.CTkLabel(
                row,
                text=date_str,
                font=ctk.CTkFont(family="Consolas", size=11),
                text_color=_COLORS["muted"]
            ).pack(side="left", padx=12)
            btn_del = ctk.CTkButton(
                row,
                text="Delete",
                fg_color="transparent",
                text_color=_COLORS["fail"],
                hover_color="#2A1414",
                width=50,
                height=26,
                corner_radius=6,
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda k=key: self._delete_invite_clicked(k)
            )
            btn_del.pack(side="right", padx=(4, 12))
            btn_copy = ctk.CTkButton(
                row,
                text="Copy",
                fg_color="#1E1C2E",
                hover_color=_COLORS["border"],
                text_color=_COLORS["accent"],
                width=50,
                height=26,
                corner_radius=6,
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda k=key: self._copy_invite_clicked(k)
            )
            btn_copy.pack(side="right", padx=4)
        self.on_status(f"Loaded {len(keys)} access codes.")

    def _copy_invite_clicked(self, key: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(key)
        self.update()
        self.on_status(f"Access key copied: {key}")

    def _generate_invite_clicked(self) -> None:
        toplevel = self.winfo_toplevel()
        if not getattr(toplevel, "is_authenticated", False) or not getattr(toplevel, "is_admin", False):
            logger.warning("Unauthorized generate invite attempt blocked.")
            return
        self._btn_gen_invite.configure(state="disabled", text="Generating...")
        def _gen():
            try:
                res = self.handler.admin_create_invite()
                new_key = res.get("key", "")
                self.after(0, lambda: messagebox.showinfo("Generated", f"Invite Key Created:\n\n{new_key}"))
                self.after(0, self._refresh_invites)
            except Exception as e:
                err = str(e)
                self.after(0, lambda: messagebox.showerror("Error", f"Failed to generate invite: {err}"))
            finally:
                self.after(0, lambda: self._btn_gen_invite.configure(state="normal", text="Generate Access Key"))
        threading.Thread(target=_gen, daemon=True).start()

    def _delete_invite_clicked(self, key: str) -> None:
        toplevel = self.winfo_toplevel()
        if not getattr(toplevel, "is_authenticated", False) or not getattr(toplevel, "is_admin", False):
            logger.warning("Unauthorized delete invite attempt blocked.")
            return
        if not messagebox.askyesno("Confirm Delete", f"Delete invite key '{key}'?"):
            return
        def _del():
            try:
                msg = self.handler.admin_delete_invite(key)
                self.after(0, lambda: self.on_status(msg))
                self.after(0, self._refresh_invites)
            except Exception as e:
                err = str(e)
                self.after(0, lambda: messagebox.showerror("Error", f"Failed to delete invite: {err}"))
        threading.Thread(target=_del, daemon=True).start()

    def _build_config_tab(self) -> None:
        scroll = ctk.CTkScrollableFrame(self._tab_config, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10, pady=10)
        grid = ctk.CTkFrame(scroll, fg_color="transparent")
        grid.pack(fill="x", padx=20, pady=10)
        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=2)
        ctk.CTkLabel(grid, text="Latest Version String:", font=ctk.CTkFont(weight="bold", size=12), text_color=_COLORS["text"]).grid(row=0, column=0, padx=10, pady=8, sticky="w")
        self._ent_version = ctk.CTkEntry(grid, fg_color=_COLORS["bg"], border_color=_COLORS["border"], height=32, corner_radius=8)
        self._ent_version.insert(0, config.CURRENT_VERSION)
        self._ent_version.grid(row=0, column=1, padx=10, pady=8, sticky="ew")
        ctk.CTkLabel(grid, text="Update ZIP Download URL:", font=ctk.CTkFont(weight="bold", size=12), text_color=_COLORS["text"]).grid(row=1, column=0, padx=10, pady=8, sticky="w")
        self._ent_url = ctk.CTkEntry(grid, fg_color=_COLORS["bg"], border_color=_COLORS["border"], height=32, corner_radius=8)
        self._ent_url.grid(row=1, column=1, padx=10, pady=8, sticky="ew")
        ctk.CTkLabel(grid, text="Public Server Announcements:", font=ctk.CTkFont(weight="bold", size=12), text_color=_COLORS["text"]).grid(row=2, column=0, padx=10, pady=8, sticky="w")
        self._ent_announcement = ctk.CTkEntry(grid, fg_color=_COLORS["bg"], border_color=_COLORS["border"], height=32, corner_radius=8)
        self._ent_announcement.grid(row=2, column=1, padx=10, pady=8, sticky="ew")
        ctk.CTkLabel(grid, text="Release Changelog Description:", font=ctk.CTkFont(weight="bold", size=12), text_color=_COLORS["text"]).grid(row=3, column=0, padx=10, pady=8, sticky="nw")
        self._txt_changelog = ctk.CTkTextbox(grid, height=120, fg_color=_COLORS["bg"], border_width=1, border_color=_COLORS["border"], corner_radius=8)
        self._txt_changelog.grid(row=3, column=1, padx=10, pady=8, sticky="ew")
        self._btn_push_config = ctk.CTkButton(
            scroll,
            text="Broadcast System Config & Version Update",
            fg_color=_COLORS["pink"],
            hover_color=_COLORS["pink_hover"],
            text_color="#FFFFFF",
            font=ctk.CTkFont(weight="bold", size=13),
            height=42,
            corner_radius=20,
            command=self._push_config_clicked
        )
        self._btn_push_config.pack(pady=20, padx=30, fill="x")

    def _push_config_clicked(self) -> None:
        toplevel = self.winfo_toplevel()
        if not getattr(toplevel, "is_authenticated", False) or not getattr(toplevel, "is_admin", False):
            logger.warning("Unauthorized push config attempt blocked.")
            return
        version = self._ent_version.get().strip()
        url = self._ent_url.get().strip()
        ann = self._ent_announcement.get().strip()
        changelog = self._txt_changelog.get("1.0", "end").strip()
        if not version:
            messagebox.showerror("Error", "Version string is required to submit version changes.")
            return
        self._btn_push_config.configure(state="disabled", text="Broadcasting...")
        def _push():
            try:
                msg = self.handler.admin_set_version(version, url, changelog, ann)
                self.after(0, lambda: messagebox.showinfo("Broadcast Sent", msg))
            except Exception as e:
                err = str(e)
                self.after(0, lambda: messagebox.showerror("Error", f"Failed to push version config: {err}"))
            finally:
                self.after(0, lambda: self._btn_push_config.configure(state="normal", text="Broadcast System Config & Version Update"))
        threading.Thread(target=_push, daemon=True).start()

    def _build_logs_tab(self) -> None:
        self._tab_logs.grid_columnconfigure(0, weight=1)
        self._tab_logs.grid_rowconfigure(0, weight=0)
        self._tab_logs.grid_rowconfigure(1, weight=1)
        sel_frame = ctk.CTkFrame(self._tab_logs, fg_color="transparent")
        sel_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=4)
        self._log_type_menu = ctk.CTkOptionMenu(
            sel_frame,
            values=["Authentication Logs", "Security Audits", "Local Diagnostics"],
            fg_color="#181B27",
            button_color=_COLORS["pink"],
            button_hover_color=_COLORS["pink_hover"],
            dropdown_fg_color=_COLORS["surface"],
            height=32,
            width=180,
            corner_radius=8,
            command=lambda v: self._refresh_logs()
        )
        self._log_type_menu.pack(side="left", padx=4)
        self._btn_refresh_logs = ctk.CTkButton(
            sel_frame,
            text="Refresh logs",
            fg_color="transparent",
            border_width=1,
            border_color=_COLORS["border"],
            text_color=_COLORS["text"],
            hover_color="#1A1C28",
            height=32,
            width=100,
            corner_radius=8,
            command=self._refresh_logs
        )
        self._btn_refresh_logs.pack(side="left", padx=8)
        self._btn_wipe_logs = ctk.CTkButton(
            sel_frame,
            text="Clear Local Diagnostics",
            fg_color="#3A0808",
            hover_color="#500A0A",
            text_color=_COLORS["fail"],
            height=32,
            corner_radius=8,
            command=self._wipe_local_logs_clicked
        )
        self._btn_wipe_logs.pack(side="right", padx=4)
        self._txt_logs = ctk.CTkTextbox(
            self._tab_logs,
            fg_color="#06070B",
            border_width=1,
            border_color="#1F2035",
            corner_radius=12,
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color="#ECEFF4",
            state="disabled"
        )
        self._txt_logs.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

    def _refresh_logs(self) -> None:
        log_type = self._log_type_menu.get()
        self.on_status(f"Refreshing {log_type}...")
        if log_type == "Local Diagnostics":
            self._btn_wipe_logs.grid()
            self._load_local_logs()
        else:
            self._btn_wipe_logs.grid_remove()
            self._load_server_logs(log_type)

    def _load_local_logs(self) -> None:
        try:
            log_path = config.LOG_FILE
            if log_path.exists():
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                    content = "".join(lines[-300:])
            else:
                content = "No local diagnostics logs generated yet."
            self._update_log_display(content, color="#5EEAD4")
            self.on_status("Loaded local diagnostics logs.")
        except Exception as e:
            self._update_log_display(f"Failed to read local log: {e}", color=_COLORS["fail"])

    def _wipe_local_logs_clicked(self) -> None:
        if not messagebox.askyesno("Confirm Clear", "Are you sure you want to delete all local diagnostics?"):
            return
        try:
            log_path = config.LOG_FILE
            if log_path.exists():
                with open(log_path, "w", encoding="utf-8") as f:
                    f.write(f"--- LOGS Wiped by Admin at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            self._load_local_logs()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to clear logs: {e}")

    def _load_server_logs(self, log_type: str) -> None:
        def _fetch():
            try:
                if log_type == "Authentication Logs":
                    data = self.handler.admin_get_login_history()
                    text = self._format_login_history(data)
                else:
                    data = self.handler.admin_get_audit_logs()
                    text = self._format_audit_logs(data)
                self.after(0, lambda: self._update_log_display(text, color="#ECEFF4"))
            except Exception as e:
                err = str(e)
                self.after(0, lambda: self._update_log_display(f"Failed to fetch logs: {err}", color=_COLORS["fail"]))
        threading.Thread(target=_fetch, daemon=True).start()

    def _update_log_display(self, text: str, color: str) -> None:
        self._txt_logs.configure(state="normal")
        self._txt_logs.delete("1.0", "end")
        self._txt_logs.configure(text_color=color)
        self._txt_logs.insert("1.0", text)
        self._txt_logs.see("end")
        self._txt_logs.configure(state="disabled")

    def _format_login_history(self, history: list) -> str:
        if not history:
            return "No server login attempts recorded."
        lines = []
        lines.append(f"{'TIMESTAMP':<20} | {'USERNAME':<16} | {'IP ADDRESS':<16} | {'STATUS':<15}")
        lines.append("-" * 75)
        for r in history:
            ts = r.get("timestamp", "")[:19]
            user = r.get("username", "")[:16]
            ip = r.get("ip_address", "")[:16]
            status = r.get("status", "")[:15]
            lines.append(f"{ts:<20} | {user:<16} | {ip:<16} | {status:<15}")
        return "\n".join(lines)

    def _format_audit_logs(self, audits: list) -> str:
        if not audits:
            return "No security audits logged on the server."
        lines = []
        lines.append(f"{'TIMESTAMP':<20} | {'ACTOR':<16} | {'ACTION':<24} | {'DETAILS'}")
        lines.append("-" * 90)
        for r in audits:
            ts = r.get("timestamp", "")[:19]
            actor = r.get("actor", "")[:16]
            action = r.get("action", "")[:24]
            details = r.get("details", "")
            lines.append(f"{ts:<20} | {actor:<16} | {action:<24} | {details}")
        return "\n".join(lines)

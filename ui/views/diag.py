import threading
import tkinter as tk
import customtkinter as ctk
from typing import Optional, Callable
from pathlib import Path
import os

from config import config
from services.diag_service import DiagnosticsService, DiagnosticReport, PhaseResult
from services.env_service import DependencyService
import core.safe as safe_mode

_COLORS = {
    "bg":       "#0A0B10",
    "surface":  "#12141C",
    "border":   "#252838",
    "pass":     "#22C55E",
    "fail":     "#EF4444",
    "warn":     "#F59E0B",
    "skip":     "#6B7280",
    "text":     "#F3F4F6",
    "muted":    "#9CA3AF",
    "accent":   "#6366F1",
}

_STATUS_ICONS = {
    "pass":    ("✓ PASS", _COLORS["pass"]),
    "fail":    ("✗ FAIL", _COLORS["fail"]),
    "warn":    ("⚠ WARN", _COLORS["warn"]),
    "skip":    ("○ SKIP", _COLORS["skip"]),
    "running": ("⟳ ...",  _COLORS["accent"]),
    "pending": ("—",       _COLORS["muted"]),
}

_PHASE_NAMES = [
    "Startup",
    "Authentication",
    "Dependencies",
    "Capture System",
    "Gesture System",
    "AI Pipeline",
    "Overlay System",
]

class DiagnosticsView(ctk.CTkFrame):
    def __init__(self, parent, auth_handler=None, session_token: str = "", **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.auth_handler = auth_handler
        self.session_token = session_token
        self._running = False
        self._last_report: Optional[DiagnosticReport] = None
        self._phase_rows: dict = {}
        self._dependency_service = DependencyService()
        self._build()

    def _build(self) -> None:
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=0, pady=(10, 0))
        left_header = ctk.CTkFrame(header, fg_color="transparent")
        left_header.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            left_header,
            text="Diagnostics & Test Center",
            font=ctk.CTkFont(family="Segoe UI Variable", size=24, weight="bold"),
            text_color=_COLORS["text"]
        ).pack(anchor="w")
        if safe_mode.is_active():
            reasons = "; ".join(safe_mode.get_reasons())
            ctk.CTkLabel(
                left_header,
                text=f"⚠ SAFE MODE — {reasons}",
                font=ctk.CTkFont(family="Segoe UI Variable", size=12, weight="bold"),
                text_color=_COLORS["warn"],
                fg_color="#1F1700",
                corner_radius=6,
                height=28
            ).pack(anchor="w", pady=(4, 0))
        else:
            ctk.CTkLabel(
                left_header,
                text="Run a complete system test. Results written to test.log.",
                font=ctk.CTkFont(family="Segoe UI Variable", size=13),
                text_color=_COLORS["muted"]
            ).pack(anchor="w", pady=(2, 0))
        btn_row = ctk.CTkFrame(header, fg_color="transparent")
        btn_row.pack(side="right", padx=0)
        self._btn_run = ctk.CTkButton(
            btn_row,
            text="Run Full Diagnostic",
            fg_color=_COLORS["accent"],
            hover_color="#4F46E5",
            height=38,
            corner_radius=10,
            font=ctk.CTkFont(family="Segoe UI Variable", weight="bold", size=13),
            command=self._on_run_clicked
        )
        self._btn_run.pack(side="left", padx=(0, 8))
        self._btn_test_ai = ctk.CTkButton(
            btn_row,
            text="Test AI Request",
            fg_color="transparent",
            border_width=1,
            border_color=_COLORS["border"],
            text_color=_COLORS["accent"],
            hover_color="#1A1C28",
            height=38,
            corner_radius=10,
            font=ctk.CTkFont(family="Segoe UI Variable", weight="bold", size=13),
            command=self._on_test_ai_clicked
        )
        self._btn_test_ai.pack(side="left", padx=(0, 8))
        self._btn_copy = ctk.CTkButton(
            btn_row,
            text="Copy Report",
            fg_color="transparent",
            border_width=1,
            border_color=_COLORS["border"],
            text_color=_COLORS["muted"],
            hover_color="#1A1C28",
            height=38,
            corner_radius=10,
            font=ctk.CTkFont(family="Segoe UI Variable", weight="bold", size=13),
            command=self._copy_report,
            state="disabled"
        )
        self._btn_copy.pack(side="left", padx=(0, 8))
        self._btn_open_log = ctk.CTkButton(
            btn_row,
            text="Open Log File",
            fg_color="transparent",
            border_width=1,
            border_color=_COLORS["border"],
            text_color=_COLORS["muted"],
            hover_color="#1A1C28",
            height=38,
            corner_radius=10,
            font=ctk.CTkFont(family="Segoe UI Variable", weight="bold", size=13),
            command=self._open_log_file,
            state="disabled"
        )
        self._btn_open_log.pack(side="left")
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", pady=(16, 0))
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=2)
        self._build_phases_panel(content)
        right_col = ctk.CTkFrame(content, fg_color="transparent")
        right_col.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        right_col.grid_rowconfigure(0, weight=2)
        right_col.grid_rowconfigure(1, weight=1)
        right_col.grid_columnconfigure(0, weight=1)
        self._build_details_panel(right_col)
        self._build_setup_panel(right_col)

    def _build_phases_panel(self, parent) -> None:
        container = ctk.CTkFrame(
            parent,
            fg_color=_COLORS["surface"],
            border_width=1,
            border_color=_COLORS["border"],
            corner_radius=16
        )
        container.grid(row=0, column=0, sticky="nsew")
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(1, weight=1)
        hdr = ctk.CTkFrame(container, fg_color="transparent", height=36)
        hdr.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 8))
        ctk.CTkLabel(
            hdr, text="DIAGNOSTIC PHASES",
            font=ctk.CTkFont(family="Segoe UI Variable", size=11, weight="bold"),
            text_color=_COLORS["muted"]
        ).pack(side="left")
        self._lbl_overall = ctk.CTkLabel(
            hdr, text="",
            font=ctk.CTkFont(family="Segoe UI Variable", size=13, weight="bold"),
            text_color=_COLORS["muted"]
        )
        self._lbl_overall.pack(side="right")
        scroll = ctk.CTkScrollableFrame(container, fg_color="transparent")
        scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 12))
        scroll.grid_columnconfigure(0, weight=1)
        for idx, phase_name in enumerate(_PHASE_NAMES):
            row_frame = ctk.CTkFrame(
                scroll,
                fg_color="#0D0E15",
                border_width=1,
                border_color="#1A1C28",
                corner_radius=8,
                height=50
            )
            row_frame.grid(row=idx, column=0, sticky="ew", padx=4, pady=3)
            row_frame.grid_columnconfigure(1, weight=1)
            status_lbl = ctk.CTkLabel(
                row_frame,
                text="—",
                font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
                text_color=_COLORS["muted"],
                width=70,
                anchor="center"
            )
            status_lbl.grid(row=0, column=0, padx=(12, 8), pady=12)
            text_col = ctk.CTkFrame(row_frame, fg_color="transparent")
            text_col.grid(row=0, column=1, sticky="ew", pady=8)
            name_lbl = ctk.CTkLabel(
                text_col,
                text=phase_name,
                font=ctk.CTkFont(family="Segoe UI Variable", size=12, weight="bold"),
                text_color=_COLORS["text"],
                anchor="w"
            )
            name_lbl.pack(anchor="w")
            msg_lbl = ctk.CTkLabel(
                text_col,
                text="Waiting...",
                font=ctk.CTkFont(family="Segoe UI Variable", size=11),
                text_color=_COLORS["muted"],
                anchor="w",
                wraplength=300
            )
            msg_lbl.pack(anchor="w")
            row_frame.bind("<Button-1>", lambda e, pn=phase_name: self._on_phase_clicked(pn))
            status_lbl.bind("<Button-1>", lambda e, pn=phase_name: self._on_phase_clicked(pn))
            name_lbl.bind("<Button-1>", lambda e, pn=phase_name: self._on_phase_clicked(pn))
            self._phase_rows[phase_name] = {
                "row": row_frame,
                "status": status_lbl,
                "msg": msg_lbl
            }

    def _build_details_panel(self, parent) -> None:
        panel = ctk.CTkFrame(
            parent,
            fg_color=_COLORS["surface"],
            border_width=1,
            border_color=_COLORS["border"],
            corner_radius=16
        )
        panel.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(
            panel,
            text="FAILURE DETAILS",
            font=ctk.CTkFont(family="Segoe UI Variable", size=11, weight="bold"),
            text_color=_COLORS["muted"]
        ).grid(row=0, column=0, padx=16, pady=(14, 6), sticky="w")
        self._detail_box = ctk.CTkTextbox(
            panel,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#0A0B10",
            border_width=0,
            wrap="word",
            state="disabled"
        )
        self._detail_box.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 12))

    def _build_setup_panel(self, parent) -> None:
        panel = ctk.CTkFrame(
            parent,
            fg_color=_COLORS["surface"],
            border_width=1,
            border_color=_COLORS["border"],
            corner_radius=16
        )
        panel.grid(row=1, column=0, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            panel,
            text="SETUP CENTER",
            font=ctk.CTkFont(family="Segoe UI Variable", size=11, weight="bold"),
            text_color=_COLORS["muted"]
        ).grid(row=0, column=0, padx=16, pady=(14, 6), sticky="w")
        setup_items = [
            "AI Engine",
        ]
        self._setup_status_labels = {}
        for idx, item in enumerate(setup_items):
            row = ctk.CTkFrame(panel, fg_color="transparent", height=28)
            row.grid(row=idx + 1, column=0, sticky="ew", padx=16, pady=2)
            row.grid_columnconfigure(1, weight=1)
            dot = ctk.CTkLabel(
                row, text="🟡",
                font=ctk.CTkFont(size=11),
                width=20
            )
            dot.grid(row=0, column=0)
            lbl = ctk.CTkLabel(
                row, text=item,
                font=ctk.CTkFont(family="Segoe UI Variable", size=12),
                text_color=_COLORS["text"],
                anchor="w"
            )
            lbl.grid(row=0, column=1, padx=(6, 0), sticky="w")
            self._setup_status_labels[item] = (dot, lbl)
        
        act_frame = ctk.CTkFrame(panel, fg_color="transparent")
        act_frame.grid(row=10, column=0, padx=16, pady=12, sticky="ew")
        act_frame.grid_columnconfigure(0, weight=1)
        self._btn_recheck_deps = ctk.CTkButton(
            act_frame,
            text="Recheck Status",
            fg_color="transparent",
            border_width=1,
            border_color=_COLORS["border"],
            text_color=_COLORS["accent"],
            hover_color="#1A1C28",
            height=32,
            corner_radius=8,
            command=self._recheck_dependencies,
            font=ctk.CTkFont(family="Segoe UI Variable", weight="bold", size=11)
        )
        self._btn_recheck_deps.grid(row=0, column=0, sticky="ew")

    def _on_run_clicked(self) -> None:
        if self._running:
            return
        toplevel = self.winfo_toplevel()
        if not getattr(toplevel, "is_authenticated", False) and not safe_mode.is_active():
            logger.warning("Diagnostics run blocked for unauthenticated session.")
            return
        self._reset_phase_display()
        self._run_diagnostics()

    def _run_diagnostics(self) -> None:
        self._running = True
        self._btn_run.configure(text="Running...", state="disabled")
        self._btn_test_ai.configure(state="disabled")
        self._btn_copy.configure(state="disabled")
        self._btn_open_log.configure(state="disabled")
        self._lbl_overall.configure(text="", text_color=_COLORS["muted"])
        threading.Thread(target=self._diagnostics_thread, daemon=True).start()

    def _diagnostics_thread(self) -> None:
        try:
            svc = DiagnosticsService(
                auth_handler=self.auth_handler,
                session_token=self.session_token
            )
            svc.set_progress_callback(self._on_progress)
            report = svc.run(safe_mode=safe_mode.is_active())
            self._last_report = report
            svc.write_test_log(report)
            self.after(0, lambda: self._on_diagnostics_complete(report))
        except Exception as e:
            err = str(e)
            self.after(0, lambda: self._on_diagnostics_error(err))

    def _on_test_ai_clicked(self) -> None:
        if self._running:
            return
        toplevel = self.winfo_toplevel()
        if not getattr(toplevel, "is_authenticated", False) and not safe_mode.is_active():
            return
        self._running = True
        self._btn_test_ai.configure(text="Testing AI...", state="disabled")
        self._btn_run.configure(state="disabled")
        self._btn_copy.configure(state="disabled")
        self._btn_open_log.configure(state="disabled")
        self._update_phase_row("AI Pipeline", "running", "Sending minimal test request...")
        self._detail_box.configure(state="normal")
        self._detail_box.delete("1.0", "end")
        self._detail_box.insert("end", "Executing live AI Request Test...\n- Validating active API key\n- Sending minimal test request\n- Checking model response\n- Verifying overlay presentation\n")
        self._detail_box.configure(state="disabled")
        threading.Thread(target=self._test_ai_thread, daemon=True).start()

    def _test_ai_thread(self) -> None:
        try:
            svc = DiagnosticsService(
                auth_handler=self.auth_handler,
                session_token=self.session_token
            )
            res = svc.test_ai_request()
            self.after(0, lambda: self._on_test_ai_complete(res))
        except Exception as e:
            err = str(e)
            self.after(0, lambda: self._on_test_ai_error(err))

    def _on_test_ai_complete(self, res: dict) -> None:
        self._running = False
        self._btn_test_ai.configure(text="Test AI Request", state="normal")
        self._btn_run.configure(text="Run Full Diagnostic", state="normal")
        self._btn_copy.configure(state="normal")
        self._btn_open_log.configure(state="normal")

        status = res.get("status", "Unknown")
        provider = res.get("provider", config.ACTIVE_PROVIDER)
        model = res.get("model", config.ACTIVE_MODEL)
        duration = res.get("duration_sec", 0.0)
        message = res.get("message", "")
        error_code = res.get("error_code", "")
        overlay_ok = res.get("overlay_tested", False)
        resp_text = res.get("response_text", "")

        is_success = (status == "API request succeeded")
        phase_status = "pass" if is_success else ("warn" if error_code == "MISSING_KEY" else "fail")
        phase_msg = f"{provider.capitalize()} ({model}) in {duration:.2f}s" if is_success else f"{status}: {message}"
        self._update_phase_row("AI Pipeline", phase_status, phase_msg)

        if "AI Engine" in self._setup_status_labels:
            dot_lbl, _ = self._setup_status_labels["AI Engine"]
            dot_lbl.configure(text="🟢" if is_success else ("🟡" if error_code == "MISSING_KEY" else "🔴"))

        self._detail_box.configure(state="normal")
        self._detail_box.delete("1.0", "end")
        lines = [
            f"{'✓' if is_success else '✗'} AI REQUEST TEST RESULT",
            "=" * 48,
            f"Status:         {status}",
            f"Provider:       {provider.capitalize()}",
            f"Model:          {model}",
            f"Duration:       {duration:.2f}s",
            f"Error Category: {error_code}",
            f"Overlay Display:{' Verified (PASS)' if overlay_ok else ' Not tested / Failed'}",
            "-" * 48,
        ]
        if is_success:
            lines.append(f"Answer Received:\n  {resp_text}")
        else:
            lines.append(f"Message:\n  {message}")
        self._detail_box.insert("end", "\n".join(lines))
        self._detail_box.configure(state="disabled")

    def _on_test_ai_error(self, error: str) -> None:
        self._running = False
        self._btn_test_ai.configure(text="Test AI Request", state="normal")
        self._btn_run.configure(text="Run Full Diagnostic", state="normal")
        self._btn_copy.configure(state="normal")
        self._btn_open_log.configure(state="normal")
        self._update_phase_row("AI Pipeline", "fail", f"Test error: {error}")
        self._detail_box.configure(state="normal")
        self._detail_box.delete("1.0", "end")
        self._detail_box.insert("end", f"AI Request Test Failed with Exception:\n\n{error}")
        self._detail_box.configure(state="disabled")

    def _on_progress(self, phase_name: str, status: str, message: str = "") -> None:
        self.after(0, lambda: self._update_phase_row(phase_name, status, message))

    def _update_phase_row(self, phase_name: str, status: str, message: str = "") -> None:
        if phase_name not in self._phase_rows:
            return
        row_widgets = self._phase_rows[phase_name]
        icon_text, icon_color = _STATUS_ICONS.get(status, ("?", _COLORS["muted"]))
        row_widgets["status"].configure(text=icon_text, text_color=icon_color)
        if message:
            row_widgets["msg"].configure(text=message)
        bg_colors = {
            "pass": "#0D120E",
            "fail": "#130909",
            "warn": "#121008",
            "skip": "#0D0E15",
            "running": "#0D0E1A",
        }
        row_widgets["row"].configure(fg_color=bg_colors.get(status, "#0D0E15"))

    def _on_diagnostics_complete(self, report: DiagnosticReport) -> None:
        self._running = False
        self._btn_run.configure(text="Run Full Diagnostic", state="normal")
        self._btn_test_ai.configure(state="normal")
        self._btn_copy.configure(state="normal")
        self._btn_open_log.configure(state="normal")
        for phase in report.phases:
            self._update_phase_row(phase.phase, phase.status, phase.message)
        if report.overall == "pass":
            self._lbl_overall.configure(text="PASS ✓", text_color=_COLORS["pass"])
        else:
            failures = report.get_failures()
            count = len(failures)
            self._lbl_overall.configure(
                text=f"FAIL — {count} issue{'s' if count > 1 else ''}",
                text_color=_COLORS["fail"]
            )
            if failures:
                self._show_phase_detail(failures[0])
        self._refresh_setup_status(report)

    def _on_diagnostics_error(self, error: str) -> None:
        self._running = False
        self._btn_run.configure(text="Run Full Diagnostic", state="normal")
        self._btn_test_ai.configure(state="normal")
        self._lbl_overall.configure(text=f"ERROR: {error}", text_color=_COLORS["fail"])

    def _on_phase_clicked(self, phase_name: str) -> None:
        if not self._last_report:
            return
        for phase in self._last_report.phases:
            if phase.phase == phase_name:
                self._show_phase_detail(phase)
                return

    def _show_phase_detail(self, phase: PhaseResult) -> None:
        self._detail_box.configure(state="normal")
        self._detail_box.delete("1.0", "end")
        if phase.status == "pass":
            self._detail_box.insert("end", f"✓ {phase.phase}\n\n{phase.message}")
        elif phase.status == "skip":
            self._detail_box.insert("end", f"○ {phase.phase}\n\nSkipped.")
        else:
            lines = [f"{'✗' if phase.status == 'fail' else '⚠'} {phase.phase}\n"]
            if phase.message:
                lines.append(f"Message:\n  {phase.message}\n")
            if phase.module:
                lines.append(f"Module:   {phase.module}")
            if phase.function:
                lines.append(f"Function: {phase.function}")
            if phase.error:
                lines.append(f"Error:    {phase.error}")
            if phase.traceback_str and phase.traceback_str.strip() not in ["", "NoneType: None"]:
                lines.append(f"\nTraceback:\n{phase.traceback_str}")
            self._detail_box.insert("end", "\n".join(lines))
        self._detail_box.configure(state="disabled")

    def _reset_phase_display(self) -> None:
        for phase_name, widgets in self._phase_rows.items():
            widgets["status"].configure(text="—", text_color=_COLORS["muted"])
            widgets["msg"].configure(text="Waiting...")
            widgets["row"].configure(fg_color="#0D0E15")
        self._detail_box.configure(state="normal")
        self._detail_box.delete("1.0", "end")
        self._detail_box.configure(state="disabled")
        self._lbl_overall.configure(text="")

    def _refresh_setup_status(self, report: DiagnosticReport) -> None:
        ai_phase = next((p for p in report.phases if p.phase == "AI Pipeline"), None)
        mapping = {
            "AI Engine": ai_phase,
        }
        for item, phase in mapping.items():
            if item not in self._setup_status_labels:
                continue
            dot_lbl, text_lbl = self._setup_status_labels[item]
            if phase is None:
                dot_lbl.configure(text="🟡")
            elif phase.status == "pass":
                dot_lbl.configure(text="🟢")
            elif phase.status in ["fail"]:
                dot_lbl.configure(text="🔴")
            else:
                dot_lbl.configure(text="🟡")

    def _recheck_dependencies(self) -> None:
        toplevel = self.winfo_toplevel()
        if not getattr(toplevel, "is_authenticated", False) and not safe_mode.is_active():
            return
        self._on_run_clicked()

    def _copy_report(self) -> None:
        if not self._last_report:
            return
        try:
            svc = DiagnosticsService()
            text = svc.get_report_text(self._last_report)
            self.clipboard_clear()
            self.clipboard_append(text)
        except Exception:
            pass

    def _open_log_file(self) -> None:
        try:
            log_path = config.TEST_LOG_FILE
            if log_path.exists():
                os.startfile(str(log_path))
        except Exception:
            pass

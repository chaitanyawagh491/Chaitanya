import logging
import tkinter.messagebox as messagebox
import customtkinter as ctk
from typing import Callable, Optional

from config import config

logger = logging.getLogger("PreferencesView")

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
}

class PreferencesView(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        on_shortcut_changed: Callable[[str], None],
        on_select_region: Callable[[], None],
        **kwargs
    ):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.on_shortcut_changed = on_shortcut_changed
        self.on_select_region = on_select_region
        self._build()

    def _build(self) -> None:
        title_lbl = ctk.CTkLabel(
            self,
            text="System Preferences",
            font=ctk.CTkFont(family="Segoe UI Variable", size=24, weight="bold"),
            text_color=_COLORS["text"]
        )
        title_lbl.pack(anchor="w", pady=(10, 2))
        desc_lbl = ctk.CTkLabel(
            self,
            text="Manage visual analysis providers, models, API keys, and hotkeys.",
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
        self._grid = ctk.CTkFrame(scroll, fg_color="transparent")
        self._grid.pack(fill="x", padx=20, pady=10)
        self._grid.grid_columnconfigure(0, weight=1)
        self._grid.grid_columnconfigure(1, weight=1)
        row = 0

        # Provider Selection
        ctk.CTkLabel(
            self._grid,
            text="Active Vision Provider:",
            font=ctk.CTkFont(family="Segoe UI Variable", weight="bold", size=12),
            text_color=_COLORS["text"]
        ).grid(row=row, column=0, padx=15, pady=12, sticky="w")
        self._opt_provider = ctk.CTkOptionMenu(
            self._grid,
            values=["gemini", "openrouter", "openai"],
            fg_color=_COLORS["bg"],
            button_color=_COLORS["bg"],
            button_hover_color=_COLORS["border"],
            dropdown_fg_color=_COLORS["surface"],
            dropdown_hover_color=_COLORS["border"],
            dropdown_text_color=_COLORS["text"],
            font=ctk.CTkFont(family="Segoe UI Variable", size=12),
            height=32,
            corner_radius=8
        )
        self._opt_provider.set(config.ACTIVE_PROVIDER)
        self._opt_provider.grid(row=row, column=1, padx=15, pady=12, sticky="ew")
        row += 1

        # Model Selection
        ctk.CTkLabel(
            self._grid,
            text="Active Vision Model:",
            font=ctk.CTkFont(family="Segoe UI Variable", weight="bold", size=12),
            text_color=_COLORS["text"]
        ).grid(row=row, column=0, padx=15, pady=12, sticky="w")
        self._ent_model = ctk.CTkEntry(
            self._grid, font=ctk.CTkFont(family="Consolas"),
            fg_color=_COLORS["bg"], border_color=_COLORS["border"], height=32, corner_radius=8
        )
        self._ent_model.insert(0, config.ACTIVE_MODEL)
        self._ent_model.grid(row=row, column=1, padx=15, pady=12, sticky="ew")
        row += 1

        # API Keys Fields
        ctk.CTkLabel(
            self._grid,
            text="Gemini API Key:",
            font=ctk.CTkFont(family="Segoe UI Variable", weight="bold", size=12),
            text_color=_COLORS["text"]
        ).grid(row=row, column=0, padx=15, pady=12, sticky="w")
        self._ent_gemini_key = ctk.CTkEntry(
            self._grid, font=ctk.CTkFont(family="Consolas"),
            placeholder_text="Enter Gemini API Key",
            fg_color=_COLORS["bg"], border_color=_COLORS["border"], height=32, corner_radius=8,
            show="*"
        )
        self._ent_gemini_key.insert(0, config.get_api_key("gemini"))
        self._ent_gemini_key.grid(row=row, column=1, padx=15, pady=12, sticky="ew")
        row += 1

        ctk.CTkLabel(
            self._grid,
            text="OpenAI API Key:",
            font=ctk.CTkFont(family="Segoe UI Variable", weight="bold", size=12),
            text_color=_COLORS["text"]
        ).grid(row=row, column=0, padx=15, pady=12, sticky="w")
        self._ent_openai_key = ctk.CTkEntry(
            self._grid, font=ctk.CTkFont(family="Consolas"),
            placeholder_text="Enter OpenAI API Key",
            fg_color=_COLORS["bg"], border_color=_COLORS["border"], height=32, corner_radius=8,
            show="*"
        )
        self._ent_openai_key.insert(0, config.get_api_key("openai"))
        self._ent_openai_key.grid(row=row, column=1, padx=15, pady=12, sticky="ew")
        row += 1

        ctk.CTkLabel(
            self._grid,
            text="OpenRouter API Key:",
            font=ctk.CTkFont(family="Segoe UI Variable", weight="bold", size=12),
            text_color=_COLORS["text"]
        ).grid(row=row, column=0, padx=15, pady=12, sticky="w")
        self._ent_openrouter_key = ctk.CTkEntry(
            self._grid, font=ctk.CTkFont(family="Consolas"),
            placeholder_text="Enter OpenRouter API Key",
            fg_color=_COLORS["bg"], border_color=_COLORS["border"], height=32, corner_radius=8,
            show="*"
        )
        self._ent_openrouter_key.insert(0, config.get_api_key("openrouter"))
        self._ent_openrouter_key.grid(row=row, column=1, padx=15, pady=12, sticky="ew")
        row += 1

        # Fallback Configurations
        ctk.CTkLabel(
            self._grid,
            text="Enable Provider Fallback:",
            font=ctk.CTkFont(family="Segoe UI Variable", weight="bold", size=12),
            text_color=_COLORS["text"]
        ).grid(row=row, column=0, padx=15, pady=12, sticky="w")
        self._chk_fallback = ctk.CTkCheckBox(
            self._grid,
            text="",
            fg_color=_COLORS["accent"],
            hover_color=_COLORS["accent_hover"],
            corner_radius=4
        )
        if config.FALLBACK_ENABLED:
            self._chk_fallback.select()
        else:
            self._chk_fallback.deselect()
        self._chk_fallback.grid(row=row, column=1, padx=15, pady=12, sticky="w")
        row += 1

        ctk.CTkLabel(
            self._grid,
            text="Fallback Vision Provider:",
            font=ctk.CTkFont(family="Segoe UI Variable", weight="bold", size=12),
            text_color=_COLORS["text"]
        ).grid(row=row, column=0, padx=15, pady=12, sticky="w")
        self._opt_fb_provider = ctk.CTkOptionMenu(
            self._grid,
            values=["gemini", "openrouter", "openai"],
            fg_color=_COLORS["bg"],
            button_color=_COLORS["bg"],
            button_hover_color=_COLORS["border"],
            dropdown_fg_color=_COLORS["surface"],
            dropdown_hover_color=_COLORS["border"],
            dropdown_text_color=_COLORS["text"],
            font=ctk.CTkFont(family="Segoe UI Variable", size=12),
            height=32,
            corner_radius=8
        )
        self._opt_fb_provider.set(config.FALLBACK_PROVIDER)
        self._opt_fb_provider.grid(row=row, column=1, padx=15, pady=12, sticky="ew")
        row += 1

        ctk.CTkLabel(
            self._grid,
            text="Fallback Vision Model:",
            font=ctk.CTkFont(family="Segoe UI Variable", weight="bold", size=12),
            text_color=_COLORS["text"]
        ).grid(row=row, column=0, padx=15, pady=12, sticky="w")
        self._ent_fb_model = ctk.CTkEntry(
            self._grid, font=ctk.CTkFont(family="Consolas"),
            fg_color=_COLORS["bg"], border_color=_COLORS["border"], height=32, corner_radius=8
        )
        self._ent_fb_model.insert(0, config.FALLBACK_MODEL)
        self._ent_fb_model.grid(row=row, column=1, padx=15, pady=12, sticky="ew")
        row += 1

        # Overlay settings
        ctk.CTkLabel(
            self._grid,
            text="Answer Overlay Duration (seconds):",
            font=ctk.CTkFont(family="Segoe UI Variable", weight="bold", size=12),
            text_color=_COLORS["text"]
        ).grid(row=row, column=0, padx=15, pady=12, sticky="w")
        self._ent_dur = ctk.CTkEntry(
            self._grid, font=ctk.CTkFont(family="Consolas"),
            fg_color=_COLORS["bg"], border_color=_COLORS["border"], height=32, corner_radius=8
        )
        self._ent_dur.insert(0, str(config.RESPONSE_DURATION))
        self._ent_dur.grid(row=row, column=1, padx=15, pady=12, sticky="ew")
        row += 1

        # Gesture window setting
        ctk.CTkLabel(
            self._grid,
            text="Triple-Tap Detection Window (seconds):",
            font=ctk.CTkFont(family="Segoe UI Variable", weight="bold", size=12),
            text_color=_COLORS["text"]
        ).grid(row=row, column=0, padx=15, pady=12, sticky="w")
        self._ent_tap = ctk.CTkEntry(
            self._grid, font=ctk.CTkFont(family="Consolas"),
            fg_color=_COLORS["bg"], border_color=_COLORS["border"], height=32, corner_radius=8
        )
        self._ent_tap.insert(0, str(config.TRIPLE_TAP_WINDOW))
        self._ent_tap.grid(row=row, column=1, padx=15, pady=12, sticky="ew")
        row += 1

        # Shortcut setting
        ctk.CTkLabel(
            self._grid,
            text="Global Toggle Shortcut (e.g. Ctrl+Shift+S):",
            font=ctk.CTkFont(family="Segoe UI Variable", weight="bold", size=12),
            text_color=_COLORS["text"]
        ).grid(row=row, column=0, padx=15, pady=12, sticky="w")
        self._ent_shortcut = ctk.CTkEntry(
            self._grid, font=ctk.CTkFont(family="Consolas"),
            fg_color=_COLORS["bg"], border_color=_COLORS["border"], height=32, corner_radius=8
        )
        self._ent_shortcut.insert(0, config.GLOBAL_SHORTCUT)
        self._ent_shortcut.grid(row=row, column=1, padx=15, pady=12, sticky="ew")
        row += 1

        # Coordinates setting
        ctk.CTkLabel(
            self._grid,
            text="Screen Capture Coordinates:",
            font=ctk.CTkFont(family="Segoe UI Variable", weight="bold", size=12),
            text_color=_COLORS["text"]
        ).grid(row=row, column=0, padx=15, pady=12, sticky="w")
        coords_frm = ctk.CTkFrame(self._grid, fg_color="transparent")
        coords_frm.grid(row=row, column=1, padx=15, pady=12, sticky="ew")
        self.lbl_crop_coords = ctk.CTkLabel(
            coords_frm,
            text=f"Current: {config.CROP_BOX if config.CROP_BOX else 'Full Screen'}",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=_COLORS["muted"]
        )
        self.lbl_crop_coords.pack(side="left", pady=0)
        btn_select_region = ctk.CTkButton(
            coords_frm,
            text="Redefine",
            height=28,
            width=80,
            fg_color="#1E1C2E",
            hover_color=_COLORS["border"],
            border_width=1,
            border_color=_COLORS["border"],
            text_color=_COLORS["accent"],
            corner_radius=8,
            command=self._on_redefine_clicked
        )
        btn_select_region.pack(side="right", padx=0)
        row += 1

        self._lbl_status = ctk.CTkLabel(
            scroll,
            text="",
            font=ctk.CTkFont(family="Segoe UI Variable", size=12, weight="bold")
        )
        self._lbl_status.pack(pady=(10, 0))
        btn_save = ctk.CTkButton(
            scroll,
            text="Save System Configuration",
            height=40,
            fg_color=_COLORS["accent"],
            hover_color=_COLORS["accent_hover"],
            text_color="#FFFFFF",
            font=ctk.CTkFont(family="Segoe UI Variable", weight="bold", size=13),
            corner_radius=12,
            command=self._save_preferences
        )
        btn_save.pack(pady=20, padx=30, fill="x")

    def _on_redefine_clicked(self) -> None:
        toplevel = self.winfo_toplevel()
        if not getattr(toplevel, "is_authenticated", False):
            return
        if self.on_select_region:
            self.on_select_region()
            self.after(500, self._update_coords_display)

    def _update_coords_display(self) -> None:
        box_text = f"Current: {config.CROP_BOX if config.CROP_BOX else 'Full Screen'}"
        self.lbl_crop_coords.configure(text=box_text)

    def _set_status(self, text: str, is_error: bool = True) -> None:
        color = _COLORS["fail"] if is_error else _COLORS["pass"]
        self._lbl_status.configure(text=text, text_color=color)

    def _save_preferences(self) -> None:
        toplevel = self.winfo_toplevel()
        if not getattr(toplevel, "is_authenticated", False):
            logger.warning("Unauthenticated save attempt blocked.")
            return
        try:
            shortcut = self._ent_shortcut.get().strip()
            if not shortcut:
                self._set_status("Shortcut keybind cannot be empty.")
                return
            parts = [p.strip().lower() for p in shortcut.split('+') if p.strip()]
            if len(parts) < 2:
                self._set_status("Shortcut must contain at least one modifier key (Ctrl, Shift, or Alt).")
                return
            modifiers = {'ctrl', 'shift', 'alt'}
            has_modifier = any(part in modifiers for part in parts)
            if not has_modifier:
                self._set_status("Shortcut must include at least one modifier key (Ctrl, Shift, or Alt).")
                return
            non_modifiers = [part for part in parts if part not in modifiers]
            if len(non_modifiers) == 0:
                self._set_status("Shortcut must end with a non-modifier key (e.g. S, K, F1).")
                return
            if len(non_modifiers) > 1:
                self._set_status("Shortcut can only have one non-modifier key.")
                return

            # Update configurations
            config.ACTIVE_PROVIDER = self._opt_provider.get().strip()
            config.ACTIVE_MODEL = self._ent_model.get().strip()
            
            # Save API keys
            config.set_api_key("gemini", self._ent_gemini_key.get().strip())
            config.set_api_key("openai", self._ent_openai_key.get().strip())
            config.set_api_key("openrouter", self._ent_openrouter_key.get().strip())
            
            config.FALLBACK_ENABLED = bool(self._chk_fallback.get())
            config.FALLBACK_PROVIDER = self._opt_fb_provider.get().strip()
            config.FALLBACK_MODEL = self._ent_fb_model.get().strip()

            config.RESPONSE_DURATION = float(self._ent_dur.get().strip())
            config.TRIPLE_TAP_WINDOW = float(self._ent_tap.get().strip())
            config.GLOBAL_SHORTCUT = shortcut
            
            config.save_to_disk()
            if self.on_shortcut_changed:
                self.on_shortcut_changed(config.GLOBAL_SHORTCUT)
            self._set_status("✓ System configuration saved successfully.", False)
            self._update_coords_display()
        except ValueError as e:
            self._set_status(f"Failed to save: Invalid inputs ({e})")
        except Exception as e:
            self._set_status(f"Failed to save: {e}")

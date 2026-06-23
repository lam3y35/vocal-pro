"""VocalPro – History logic."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime

import customtkinter as ctk

from code._shared import (
    _BG, _CARD_TOP, _ERROR, _HISTORY_FILE, _SEP_HISTORY_FILE,
    _SUCCESS, _TEXT, _TEXT_DIM, _WARNING,
    AccentButton, DangerButton,
)
from code.config import save_config

logger = logging.getLogger(__name__)


class HistoryMixin:
    def _load_history(self) -> list[dict]:
        """Load the download history from JSON file."""
        try:
            if os.path.isfile(_HISTORY_FILE):
                with open(_HISTORY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.warning("Failed to load download history: %s", e)
            return []

    def _save_history(self) -> None:
        """Save download history to disk."""
        try:
            # Keep only the last 100 entries
            trimmed = self._download_history[-100:]
            with open(_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(trimmed, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("Failed to save download history: %s", e)

    def _add_history(self, filename: str, url: str, status: str, size: str = "") -> None:
        """Record a download history entry."""
        self._download_history.append({
            "filename": filename,
            "url": url,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "size": size,
            "status": status,
        })
        self._save_history()

    def _show_history(self) -> None:
        """Open a dialog showing download history."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Download History")
        dialog.geometry("640x400")
        dialog.configure(fg_color=_BG)
        dialog.transient(self)
        dialog.grab_set()

        header_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(16, 4))

        ctk.CTkLabel(
            header_frame,
            text="📋  Download History",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=_TEXT,
        ).pack(side="left")

        def clear_history():
            self._download_history = []
            self._save_history()
            dialog.destroy()

        DangerButton(
            header_frame, text="Clear All", width=90, height=28,
            command=clear_history,
        ).pack(side="right")

        if not self._download_history:
            ctk.CTkLabel(
                dialog,
                text="No downloads yet.",
                font=ctk.CTkFont(size=13),
                text_color=_TEXT_DIM,
            ).pack(expand=True)
            AccentButton(dialog, text="Close", width=100, command=dialog.destroy).pack(pady=(0, 20))
            return

        # ── Column headers ─────────────────────────────────────────────
        col_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        col_frame.pack(fill="x", padx=20, pady=(4, 0))

        headers = ["Status", "Filename", "Size", "Date", "URL"]
        widths = [60, 220, 70, 120, 1]  # last is expandable
        for i, (hdr, w) in enumerate(zip(headers, widths)):
            ctk.CTkLabel(
                col_frame,
                text=hdr,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=_TEXT_DIM,
                anchor="w",
            ).grid(row=0, column=i, sticky="w", padx=(0, 8))
            if w > 1:
                col_frame.grid_columnconfigure(i, weight=0, minsize=w)
            else:
                col_frame.grid_columnconfigure(i, weight=1)

        # ── Scrollable entries ─────────────────────────────────────────
        scroll = ctk.CTkScrollableFrame(dialog, fg_color="transparent", height=280)
        scroll.pack(fill="both", expand=True, padx=20, pady=(4, 12))

        for entry in reversed(self._download_history):  # newest first
            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill="x", pady=1)

            status = entry.get("status", "")
            if status == "success":
                status_icon = "✅"
                st_color = _SUCCESS
            elif status == "cancelled":
                status_icon = "✕"
                st_color = _WARNING
            else:
                status_icon = "⚠️"
                st_color = _ERROR

            values = [
                status_icon,
                entry.get("filename", ""),
                entry.get("size", ""),
                entry.get("timestamp", ""),
                entry.get("url", ""),
            ]
            for i, (val, w) in enumerate(zip(values, widths)):
                lbl = ctk.CTkLabel(
                    row,
                    text=val,
                    font=ctk.CTkFont(size=12),
                    text_color=st_color if i == 0 else _TEXT_DIM,
                    anchor="w",
                )
                lbl.grid(row=0, column=i, sticky="w", padx=(0, 8))
                if w > 1:
                    row.grid_columnconfigure(i, weight=0, minsize=w)
                else:
                    row.grid_columnconfigure(i, weight=1)

        AccentButton(dialog, text="Close", width=100, command=dialog.destroy).pack(pady=(0, 16))


    # ── Separation history ─────────────────────────────────────────

    def _load_sep_history(self) -> list[dict]:
        """Load separation history from disk."""
        try:
            if os.path.isfile(_SEP_HISTORY_FILE):
                with open(_SEP_HISTORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
        except Exception as e:
            logger.warning("Failed to load separation history: %s", e)
        return []

    def _save_sep_history(self) -> None:
        """Save separation history to disk."""
        try:
            trimmed = self._separation_history[-100:]
            with open(_SEP_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(trimmed, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("Failed to save separation history: %s", e)

    def _add_sep_history(self, files: list[str], model: str, output_folder: str,
                          status: str, settings: Optional[dict] = None) -> None:
        """Record a separation history entry."""
        self._separation_history.append({
            "files": [os.path.basename(f) for f in files],
            "full_paths": list(files),  # Store full paths for re-run capability
            "model": model,
            "output_folder": output_folder,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "status": status,
            "settings": settings or {},
        })
        self._save_sep_history()

    def _show_sep_history(self) -> None:
        """Open a dialog showing separation history."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Separation History")
        dialog.geometry("720x420")
        dialog.configure(fg_color=_BG)
        dialog.transient(self)
        dialog.grab_set()

        header_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(16, 4))

        ctk.CTkLabel(
            header_frame,
            text="🧬  Separation History",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=_TEXT,
        ).pack(side="left")

        def clear_history():
            self._separation_history = []
            self._save_sep_history()
            dialog.destroy()

        DangerButton(
            header_frame, text="Clear All", width=90, height=28,
            command=clear_history,
        ).pack(side="right")

        if not self._separation_history:
            ctk.CTkLabel(
                dialog,
                text="No separations yet.",
                font=ctk.CTkFont(size=13),
                text_color=_TEXT_DIM,
            ).pack(expand=True)
            AccentButton(dialog, text="Close", width=100, command=dialog.destroy).pack(pady=(0, 20))
            return

        # ── Column headers ─────────────────────────────────────────────
        col_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        col_frame.pack(fill="x", padx=20, pady=(4, 0))

        headers = ["Status", "Files", "Model", "Output Folder", "Date", ""]
        widths = [60, 220, 120, 1, 120, 50]  # last is expandable
        for i, (hdr, w) in enumerate(zip(headers, widths)):
            ctk.CTkLabel(
                col_frame,
                text=hdr,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=_TEXT_DIM,
                anchor="w",
            ).grid(row=0, column=i, sticky="w", padx=(0, 8))
            if w > 1:
                col_frame.grid_columnconfigure(i, weight=0, minsize=w)
            else:
                col_frame.grid_columnconfigure(i, weight=1)

        # ── Scrollable entries ─────────────────────────────────────────
        scroll = ctk.CTkScrollableFrame(dialog, fg_color="transparent", height=280)
        scroll.pack(fill="both", expand=True, padx=20, pady=(4, 12))

        for entry in reversed(self._separation_history):  # newest first
            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill="x", pady=1)

            status = entry.get("status", "")
            if status == "success":
                status_icon = "✅"
                st_color = _SUCCESS
            elif status == "cancelled":
                status_icon = "✕"
                st_color = _WARNING
            else:
                status_icon = "⚠️"
                st_color = _ERROR

            file_list = entry.get("files", [])
            files_text = ", ".join(file_list[:3])
            if len(file_list) > 3:
                files_text += f" …(+{len(file_list)-3})"

            values = [
                status_icon,
                files_text,
                entry.get("model", ""),
                entry.get("output_folder", ""),
                entry.get("timestamp", ""),
            ]
            for i, (val, w) in enumerate(zip(values, widths)):
                lbl = ctk.CTkLabel(
                    row,
                    text=val,
                    font=ctk.CTkFont(size=12),
                    text_color=st_color if i == 0 else _TEXT_DIM,
                    anchor="w",
                )
                lbl.grid(row=0, column=i, sticky="w", padx=(0, 8))
                if w > 1:
                    row.grid_columnconfigure(i, weight=0, minsize=w)
                else:
                    row.grid_columnconfigure(i, weight=1)

            # Re-run button for successful entries
            if status == "success":
                def make_rerun_cb(e):
                    return lambda: (dialog.destroy(), self._rerun_from_history(e))
                rerun_btn = ctk.CTkButton(
                    row,
                    text="↻",
                    width=32, height=22,
                    font=ctk.CTkFont(size=11),
                    fg_color="transparent",
                    hover_color=_CARD_TOP,
                    text_color=_TEXT,
                    corner_radius=4,
                    command=make_rerun_cb(entry),
                )
                rerun_btn.grid(row=0, column=len(widths) - 1, sticky="e", padx=(0, 2))

        AccentButton(dialog, text="Close", width=100, command=dialog.destroy).pack(pady=(0, 16))

    def _rerun_from_history(self, entry: dict) -> None:
        """Re-run separation using settings from a history entry."""
        # Get the full file paths from the history entry
        file_paths = entry.get("full_paths", [])
        if not file_paths:
            self.log("⚠️  No file paths in history entry — cannot re-run.")
            return

        # Check which files still exist
        existing = [f for f in file_paths if os.path.isfile(f)]
        if not existing:
            self.log("❌  None of the original files still exist on disk.")
            return

        missing = len(file_paths) - len(existing)
        if missing:
            self.log(f"⚠️  {missing} file(s) from history no longer exist — skipped.")

        # Apply the saved model
        model = entry.get("model", "")
        if model in self._model_descriptions:
            self.model_var.set(model)
            self._on_model_change()

        # Apply the saved settings
        settings = entry.get("settings", {})
        for key, val in settings.items():
            self.config[key] = val
        save_config(self.config)

        # Sync the checkbox vars with the loaded config
        self.include_sfx_var.set(bool(self.config.get("include_sfx", False)))
        self.enable_gate_var.set(bool(self.config.get("enable_vocal_gate", True)))
        self.enable_denoise_var.set(bool(self.config.get("enable_spectral_denoise", True)))
        self.gen_samples_var.set(bool(self.config.get("generate_comparison_samples", False)))
        self.save_bg_var.set(bool(self.config.get("save_background_track", False)))
        self.enable_multiband_var.set(bool(self.config.get("enable_multiband_denoise", True)))
        self.enable_profile_var.set(bool(self.config.get("enable_noise_profile", True)))
        self.adaptive_gate_var.set(bool(self.config.get("adaptive_gate_floor", True)))
        self.sfx_sep_var.set(bool(self.config.get("enable_sfx_separation", False)))

        # Set the output folder from the history entry
        out_folder = entry.get("output_folder", "")
        if out_folder and os.path.isdir(out_folder):
            self.current_output_dir = out_folder
            self.output_dir_label.configure(text=out_folder, text_color=_TEXT)

        # Load files and start separation
        self.input_files = existing
        self._update_file_label()
        self.log(f"↻  Re-running separation for {len(existing)} file(s) with {model}")
        self.start_separation()


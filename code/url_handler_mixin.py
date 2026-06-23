"""VocalPro – URLHandler logic."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import threading
import time
import urllib.request
from datetime import datetime
from urllib.parse import urlparse

import customtkinter as ctk

from code._shared import (
    _BG, _BORDER, _CARD_TOP, _ERROR, _SUPPORTED_EXTS,
    _TEXT, _TEXT_DIM, _WARNING, _PROJECT_ROOT,
    AccentButton, GhostButton,
)
from code.config import save_config


class URLHandlerMixin:
    def _probe_url(self, url: str) -> tuple[Optional[str], str]:
        """Send a HEAD request to extract the real filename (Content-Disposition)
        and Content-Type so we can pick a good extension.

        Returns (filename or None, content_type string).
        """
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=10) as resp:
                disposition = resp.headers.get("Content-Disposition", "")
                filename = None
                if disposition:
                    # Supports: filename="song.mp3" and filename*=UTF-8''song.mp3
                    m = re.search(
                        r"filename\*?=(?:UTF-8\'\')?[\"']?([^\"';\n]*)[\"']?",
                        disposition, re.I,
                    )
                    if m and m.group(1).strip():
                        filename = m.group(1).strip()
                content_type = resp.headers.get("Content-Type", "")
                return filename, content_type
        except Exception:
            return None, ""

    def _pick_filename(self, url: str) -> str:
        """Determine the best filename for a URL download.

        1. Try Content-Disposition header (gives the real name from CDNs).
        2. Fall back to the last path segment of the URL.
        3. If still no extension, infer one from Content-Type.
        """
        probed_name, content_type = self._probe_url(url)

        if probed_name:
            name = probed_name
        else:
            parsed = urlparse(url)
            name = os.path.basename(parsed.path) or "downloaded_file"

        # Ensure an extension exists
        if "." not in name:
            ct = content_type.lower()
            if "audio/mpeg" in ct:
                name += ".mp3"
            elif "audio/mp4" in ct or "video/mp4" in ct:
                name += ".m4a" if "audio/" in ct else ".mp4"
            elif "audio/wav" in ct or "audio/x-wav" in ct:
                name += ".wav"
            elif "audio/ogg" in ct or "video/ogg" in ct:
                name += ".ogg"
            elif "audio/flac" in ct or "audio/x-flac" in ct:
                name += ".flac"
            elif "audio/webm" in ct or "video/webm" in ct:
                name += ".webm"
            elif "video/" in ct:
                name += ".mp4"
            else:
                name += ".mp3"  # sensible default

        return name

    def _cancel_download(self) -> None:
        """Abort the currently active download."""
        self._download_cancel.set()
        self.btn_cancel_dload.configure(state="disabled")
        self.log("✕  Cancelling download…")

    def _retry_download(self) -> None:
        """Retry the last failed URL download."""
        if self._last_url:
            self.btn_retry.pack_forget()
            self.log(f"↻  Retrying: {self._last_url}")
            self._download_url(self._last_url)

    # ── Download history ────────────────────────────────────────────

    def _download_url(self, url: str) -> None:
        """Download a file from a URL in a background thread and load it.

        Progress is pushed to the queue so the main thread can update the
        progress bar, status badge, and log seamlessly.
        """
        if self._download_in_progress:
            self.log("⏳ A download is already in progress.")
            return
        self._download_in_progress = True
        self._last_url = url
        self._download_cancel.clear()
        self.btn_retry.pack_forget()
        self.btn_cancel_dload.configure(state="normal")
        if not self.btn_cancel_dload.winfo_manager():
            self.btn_cancel_dload.pack(side="left", padx=(6, 0))
        self.after(0, lambda: self.log(f"Downloading: {url}"))
        self.after(0, lambda: self.status_badge.set_status("Downloading…", _WARNING))
        self.after(0, lambda: self.progress_bar.set(0))

        # Capture output dir before starting thread to avoid cross-thread read
        _captured_output_dir = self.current_output_dir

        def _bg_download():
            # Use per-request timeout via urlopen context manager.
            # Avoid socket.setdefaulttimeout which is process-wide and not thread-safe.
            dl_path = None
            filename = ""
            try:
                filename = self._pick_filename(url)
                ext = os.path.splitext(filename)[1].lower()
                if ext not in _SUPPORTED_EXTS:
                    self.queue.put(("error", f"Unsupported file type: {ext}"))
                    return

                dl_dir = _captured_output_dir or os.path.join(_PROJECT_ROOT, "output_vocals")
                os.makedirs(dl_dir, exist_ok=True)

                # Avoid overwriting existing files
                dl_path = os.path.join(dl_dir, filename)
                base, ext = os.path.splitext(dl_path)
                counter = 1
                while os.path.exists(dl_path):
                    dl_path = f"{base} ({counter}){ext}"
                    counter += 1

                _last_bytes = 0
                _last_time = time.time()
                _avg_speed = 0.0  # Exponential moving average of download speed

                def reporthook(block_num: int, block_size: int, total_size: int) -> None:
                    nonlocal _last_bytes, _last_time, _avg_speed
                    # Check for user cancellation on each progress tick
                    if self._download_cancel.is_set():
                        raise RuntimeError("Cancelled")
                    downloaded = block_num * block_size
                    if total_size > 0:
                        downloaded = min(downloaded, total_size)
                        percent = downloaded / total_size * 100.0

                        # Compute current speed from delta since last tick
                        now = time.time()
                        elapsed = now - _last_time
                        if elapsed > 0:
                            instant_speed = (downloaded - _last_bytes) / elapsed
                        else:
                            instant_speed = 0.0
                        _last_bytes = downloaded
                        _last_time = now

                        # Exponential moving average to smooth speed/ETA jitter
                        # alpha=0.3 → 30% weight on newest sample, 70% on history
                        if _avg_speed == 0.0:
                            _avg_speed = instant_speed
                        else:
                            _avg_speed = 0.3 * instant_speed + 0.7 * _avg_speed

                        speed = _avg_speed
                        speed_str = self._format_size(speed) + "/s" if speed > 0 else ""

                        # Compute ETA from remaining bytes / smoothed speed
                        if speed > 0 and downloaded < total_size:
                            eta_sec = (total_size - downloaded) / speed
                            if eta_sec >= 3600:
                                eta_str = f"{int(eta_sec // 3600)}h {int((eta_sec % 3600) // 60)}m"
                            elif eta_sec >= 60:
                                eta_str = f"{int(eta_sec // 60)}m {int(eta_sec % 60)}s"
                            else:
                                eta_str = f"{int(eta_sec)}s"
                        else:
                            eta_str = ""

                        text = (
                            f"Downloading {filename}: {percent:.0f}%  "
                            f"({self._format_size(downloaded)} / {self._format_size(total_size)})"
                        )
                        extras = "  ".join(filter(None, [f"[{speed_str}]" if speed_str else "",
                                                          f"[{eta_str}]" if eta_str else ""]))
                        if extras:
                            text += "  " + extras
                    else:
                        percent = -1.0
                        text = f"Downloading {filename}: {self._format_size(downloaded)}"
                    self.queue.put(("download", percent, text))

                # Manual download with per-request timeout (urlretrieve doesn't support timeout)
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=60) as response:
                    total_size = int(response.headers.get("Content-Length", 0))
                    block_size = 8192
                    block_num = 0
                    with open(dl_path, "wb") as f:
                        while True:
                            chunk = response.read(block_size)
                            if not chunk:
                                break
                            f.write(chunk)
                            if self._download_cancel.is_set():
                                raise RuntimeError("Cancelled")
                            block_num += 1
                            downloaded = block_num * block_size
                            reporthook(block_num, block_size, total_size if total_size > 0 else -1)

                if not os.path.isfile(dl_path) or os.path.getsize(dl_path) == 0:
                    self.queue.put(("error", "Download failed – empty file"))
                    return

                size_str = self._format_size(os.path.getsize(dl_path))
                self._add_history(os.path.basename(dl_path), url, "success", size_str)
                self.queue.put(("download", 100.0,
                                f"✅  Downloaded: {os.path.basename(dl_path)}",
                                dl_path))
            except Exception as e:
                if self._download_cancel.is_set():
                    # User canceled — delete the partial file
                    if dl_path and os.path.exists(dl_path):
                        # Small retry loop for Windows file locks
                        for _ in range(3):
                            try:
                                time.sleep(0.2)
                                os.unlink(dl_path)
                                break
                            except Exception:
                                pass
                    self._add_history(filename, url, "cancelled")
                    self.queue.put(("cancelled", None))
                else:
                    msg = str(e)
                    if "timed out" in msg.lower():
                        msg = "Download timed out — server may be unreachable or too slow"
                    else:
                        msg = f"Download failed: {msg}"
                    self._add_history(filename, url, "error")
                    self.queue.put(("error", msg))
            finally:
                self._download_in_progress = False

        threading.Thread(target=_bg_download, daemon=True).start()

    def _load_from_url(self) -> None:
        """Open a lightweight dialog to enter a URL, then close it and
        download in the background — progress shows in the main window."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Load from URL")
        dialog.geometry("600x180")
        dialog.configure(fg_color=_BG)
        # Non-modal transient — stays above the main window but doesn't block it.
        dialog.transient(self)
        dialog.lift()
        dialog.focus_force()

        ctk.CTkLabel(
            dialog, text="Paste a direct link to an audio or video file:",
            font=ctk.CTkFont(size=14), text_color=_TEXT,
        ).pack(padx=20, pady=(20, 8), anchor="w")

        url_entry = ctk.CTkEntry(
            dialog, placeholder_text="https://example.com/song.mp3",
            font=ctk.CTkFont(size=13), height=38,
            fg_color=_CARD_TOP, border_color=_BORDER,
        )
        url_entry.pack(fill="x", padx=20, pady=(0, 8))
        url_entry.focus()

        status_lbl = ctk.CTkLabel(
            dialog, text="", font=ctk.CTkFont(size=12), text_color=_TEXT_DIM,
        )
        status_lbl.pack(padx=20, anchor="w")

        def do_download():
            url = url_entry.get().strip()
            if not url:
                status_lbl.configure(text="Please enter a URL", text_color=_ERROR)
                return
            if not url.startswith(("http://", "https://")):
                status_lbl.configure(text="URL must start with http:// or https://", text_color=_ERROR)
                return

            # Close dialog immediately — progress shows in the main window.
            dialog.destroy()

            self.log(f"🌐  Downloading from URL: {url}")
            self._download_url(url)

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(4, 16))

        AccentButton(btn_frame, text="Download & Load", width=150,
                     command=do_download).pack(side="left")
        GhostButton(btn_frame, text="Cancel", width=100,
                    command=dialog.destroy).pack(side="left", padx=(8, 0))

    # ── Drag-and-drop handler ───────────────────────────────────────────


"""Shared constants, paths, colors, and UI widget classes for VocalPro."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

import customtkinter as ctk

# ── Paths ────────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    _APP_DIR = os.path.dirname(sys.executable)
else:
    _APP_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_APP_DIR)

_APP_ICON = os.path.join(_PROJECT_ROOT, "vocalpro.ico")

_DATA_DIR = os.environ.get("APPDATA", os.path.expanduser("~"))
_DATA_DIR = os.path.join(_DATA_DIR, "VocalPro")
os.makedirs(_DATA_DIR, exist_ok=True)

for _old_name, _new_name in [("download_history.json", "download_history.json"),
                              ("separation_history.json", "separation_history.json")]:
    _old_path = os.path.join(_APP_DIR, _old_name)
    _new_path = os.path.join(_DATA_DIR, _new_name)
    if os.path.isfile(_old_path) and not os.path.isfile(_new_path):
        try:
            shutil.copy2(_old_path, _new_path)
        except Exception:
            pass

SHORTCUT_MARKER = os.path.join(_DATA_DIR, ".shortcut_created")
_HISTORY_FILE = os.path.join(_DATA_DIR, "download_history.json")
_SEP_HISTORY_FILE = os.path.join(_DATA_DIR, "separation_history.json")
_PRESETS_DIR = os.path.join(_DATA_DIR, "presets")
os.makedirs(_PRESETS_DIR, exist_ok=True)

# ── Color palette ────────────────────────────────────────────────────────
_BG        = "#0D1117"
_CARD_BG   = "#161B22"
_CARD_TOP  = "#21262D"
_BORDER    = "#30363D"
_ACCENT    = "#7C3AED"
_ACCENT_H  = "#6D28D9"
_SUCCESS   = "#22C55E"
_ERROR     = "#EF4444"
_WARNING   = "#F59E0B"
_TEXT      = "#E6EDF3"
_TEXT_DIM  = "#8B949E"
_DROP_BG   = "#1E293B"
_DROP_BORDER = "#7C3AED"

# ── Supported extensions ─────────────────────────────────────────────────
_SUPPORTED_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".flv", ".mp3", ".wav", ".flac", ".ogg"}

# ── Settings keys saved to separation history ────────────────────────────
_SETTINGS_KEYS = [
    "segment", "overlap", "shifts",
    "gate_threshold_db", "gate_floor_db",
    "denoise_strength",
    "large_file_threshold_minutes",
    "enable_vocal_gate", "enable_spectral_denoise",
    "enable_multiband_denoise", "enable_noise_profile",
    "adaptive_gate_floor",
    "enable_sfx_separation",
    "sfx_separation_margin_db",
    "include_sfx", "generate_comparison_samples",
    "save_background_track",
]

# ── Shortcut creation ────────────────────────────────────────────────────

def _write_shortcut_marker() -> None:
    try:
        with open(SHORTCUT_MARKER, "w") as f:
            f.write("1")
    except Exception:
        pass


def create_desktop_shortcut() -> None:
    if not getattr(sys, "frozen", False) or os.path.exists(SHORTCUT_MARKER):
        return
    exe_path = os.path.abspath(sys.executable)
    shortcut_path = os.path.expanduser("~/Desktop/VocalPro.lnk")
    working_dir = os.path.dirname(exe_path)
    if os.path.exists(shortcut_path):
        _write_shortcut_marker()
        return
    temp_files: list[str] = []
    try:
        icon_path = os.path.join(os.path.dirname(exe_path), "vocalpro.ico")
        if not os.path.isfile(icon_path):
            icon_path = os.path.join(_APP_DIR, "vocalpro.ico")
        vbs = (
            f'Set WshShell = WScript.CreateObject("WScript.Shell")\n'
            f'Set Shortcut = WshShell.CreateShortcut("{shortcut_path}")\n'
            f'Shortcut.TargetPath = "{exe_path}"\n'
            f'Shortcut.WorkingDirectory = "{working_dir}"\n'
            f'Shortcut.Description = "VocalPro - Remove Background Music"\n'
            f'If WScript.CreateObject("Scripting.FileSystemObject").FileExists("{icon_path}") Then\n'
            f'  Shortcut.IconLocation = "{icon_path},0"\n'
            f'End If\n'
            f'Shortcut.Save\n'
        )
        vbs_file = tempfile.NamedTemporaryFile(suffix=".vbs", delete=False, mode="w")
        vbs_file.write(vbs)
        vbs_file.close()
        temp_files.append(vbs_file.name)
        subprocess.run(["cscript", "//Nologo", vbs_file.name],
                       capture_output=True, text=True, timeout=10)
        if not os.path.exists(shortcut_path):
            ps = (
                f'$wshell = New-Object -ComObject WScript.Shell\n'
                f'$sc = $wshell.CreateShortcut("{shortcut_path}")\n'
                f'$sc.TargetPath = "{exe_path}"\n'
                f'$sc.WorkingDirectory = "{working_dir}"\n'
                f'$sc.Description = "VocalPro - Remove Background Music"\n'
                f'if (Test-Path "{icon_path}") {{ $sc.IconLocation = "{icon_path},0" }}\n'
                f'$sc.Save()\n'
            )
            ps_file = tempfile.NamedTemporaryFile(suffix=".ps1", delete=False, mode="w")
            ps_file.write(ps)
            ps_file.close()
            temp_files.append(ps_file.name)
            subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", ps_file.name],
                           capture_output=True, timeout=15)
    except Exception:
        pass
    finally:
        for f in temp_files:
            try:
                if os.path.exists(f):
                    os.unlink(f)
            except Exception:
                pass
        _write_shortcut_marker()


# ── Custom widgets ──────────────────────────────────────────────────────

class Card(ctk.CTkFrame):
    def __init__(self, master, title: str = "", **kw):
        kw.setdefault("fg_color", _CARD_BG)
        kw.setdefault("corner_radius", 12)
        kw.setdefault("border_width", 1)
        kw.setdefault("border_color", _BORDER)
        super().__init__(master, **kw)
        if title:
            lbl = ctk.CTkLabel(
                self, text=title,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=_TEXT_DIM,
                anchor="w",
            )
            lbl.pack(fill="x", padx=16, pady=(10, 2))
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)


class _DropTargetHandler:
    def __init__(self, widget, callback):
        self.widget = widget
        self.callback = callback
        self._hwnd = None
        self._old_proc = None
        self._proc = None
        self._register()

    def _register(self):
        import ctypes
        from ctypes import wintypes

        hwnd = self.widget.winfo_id()
        self._hwnd = hwnd

        shell32 = ctypes.windll.shell32
        user32 = ctypes.windll.user32

        shell32.DragAcceptFiles(hwnd, True)

        is_64 = ctypes.sizeof(ctypes.c_void_p) == 8
        if is_64:
            SetWindowLong = user32.SetWindowLongPtrA
            GetWindowLong = user32.GetWindowLongPtrA
        else:
            SetWindowLong = user32.SetWindowLongW
            GetWindowLong = user32.GetWindowLongW

        GWL_WNDPROC = -4
        WM_DROPFILES = 0x0233

        _LP = ctypes.c_ssize_t
        _WP = ctypes.c_size_t

        GetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int]
        GetWindowLong.restype = _LP

        SetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int, _LP]
        SetWindowLong.restype = _LP

        user32.CallWindowProcW.argtypes = [
            ctypes.c_void_p,
            wintypes.HWND,
            wintypes.UINT,
            _WP,
            _LP,
        ]
        user32.CallWindowProcW.restype = _LP

        shell32.DragQueryFileW.argtypes = [
            _WP, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT,
        ]
        shell32.DragQueryFileW.restype = wintypes.UINT
        shell32.DragFinish.argtypes = [_WP]
        shell32.DragFinish.restype = None

        self._old_proc = GetWindowLong(hwnd, GWL_WNDPROC)

        WNDPROC = ctypes.WINFUNCTYPE(
            _LP, wintypes.HWND, wintypes.UINT, _WP, _LP,
        )

        PyGILState_Ensure = ctypes.pythonapi.PyGILState_Ensure
        PyGILState_Ensure.argtypes = []
        PyGILState_Ensure.restype = ctypes.c_int

        PyGILState_Release = ctypes.pythonapi.PyGILState_Release
        PyGILState_Release.argtypes = [ctypes.c_int]
        PyGILState_Release.restype = None

        def _wnd_proc(hwnd, msg, wparam, lparam):
            if msg == WM_DROPFILES:
                state = PyGILState_Ensure()
                try:
                    count = shell32.DragQueryFileW(wparam, -1, None, 0)
                    files = []
                    buf = ctypes.create_unicode_buffer(260)
                    for i in range(count):
                        shell32.DragQueryFileW(
                            wparam, i, buf, ctypes.sizeof(buf),
                        )
                        files.append(buf.value)
                    shell32.DragFinish(wparam)
                    if self.callback:
                        self.callback("\r\n".join(files))
                finally:
                    PyGILState_Release(state)
                return _LP(0)
            return user32.CallWindowProcW(
                self._old_proc, hwnd, msg, wparam, lparam,
            )

        self._proc = WNDPROC(_wnd_proc)
        SetWindowLong(hwnd, GWL_WNDPROC, self._proc)

    def __del__(self):
        try:
            if self._hwnd is not None and self._old_proc is not None:
                import ctypes
                user32 = ctypes.windll.user32
                _LP = ctypes.c_ssize_t
                is_64 = ctypes.sizeof(ctypes.c_void_p) == 8
                if is_64:
                    user32.SetWindowLongPtrA.argtypes = [
                        ctypes.wintypes.HWND, ctypes.c_int, _LP,
                    ]
                    user32.SetWindowLongPtrA.restype = _LP
                    user32.SetWindowLongPtrA(self._hwnd, -4, _LP(self._old_proc))
                else:
                    user32.SetWindowLongW.argtypes = [
                        ctypes.wintypes.HWND, ctypes.c_int, ctypes.c_long,
                    ]
                    user32.SetWindowLongW.restype = ctypes.c_long
                    user32.SetWindowLongW(self._hwnd, -4, int(self._old_proc))
        except Exception:
            pass


class DropZone(ctk.CTkFrame):
    def __init__(self, master, on_drop=None, **kw):
        kw.setdefault("fg_color", _CARD_TOP)
        kw.setdefault("corner_radius", 10)
        kw.setdefault("border_width", 2)
        kw.setdefault("border_color", _BORDER)
        kw.setdefault("height", 64)
        super().__init__(master, **kw)
        self.pack_propagate(False)
        self.on_drop = on_drop
        self._is_hovering = False
        self.label = ctk.CTkLabel(
            self,
            text="🎯  Drag & drop a file here",
            font=ctk.CTkFont(size=13),
            text_color=_TEXT_DIM,
        )
        self.label.pack(expand=True)
        try:
            self._drop_target = _DropTargetHandler(self, self._on_native_drop)
        except Exception:
            self.label.configure(text="📁  Click Browse to select a file")

    def _on_native_drop(self, data):
        self.configure(border_color=_BORDER, fg_color=_CARD_TOP)
        self.label.configure(
            text="🎯  Drag & drop a file here",
            text_color=_TEXT_DIM,
        )
        if self.on_drop:
            self.after(0, self.on_drop, data)

    def set_file(self, filename: str) -> None:
        self.label.configure(text=f"✅  {filename}", text_color=_SUCCESS)

    def reset(self) -> None:
        self.label.configure(
            text="🎯  Drag & drop a file here",
            text_color=_TEXT_DIM,
        )


class AccentButton(ctk.CTkButton):
    def __init__(self, master, **kw):
        kw.setdefault("fg_color", _ACCENT)
        kw.setdefault("hover_color", _ACCENT_H)
        kw.setdefault("text_color", "#FFFFFF")
        kw.setdefault("corner_radius", 8)
        kw.setdefault("height", 34)
        kw.setdefault("font", ctk.CTkFont(size=13, weight="bold"))
        super().__init__(master, **kw)


class GhostButton(ctk.CTkButton):
    def __init__(self, master, **kw):
        kw.setdefault("fg_color", "transparent")
        kw.setdefault("hover_color", _CARD_TOP)
        kw.setdefault("text_color", _TEXT)
        kw.setdefault("corner_radius", 8)
        kw.setdefault("height", 34)
        kw.setdefault("border_width", 1)
        kw.setdefault("border_color", _BORDER)
        kw.setdefault("font", ctk.CTkFont(size=13))
        super().__init__(master, **kw)


class DangerButton(ctk.CTkButton):
    def __init__(self, master, **kw):
        kw.setdefault("fg_color", "#7F1D1D")
        kw.setdefault("hover_color", "#991B1B")
        kw.setdefault("text_color", "#FCA5A5")
        kw.setdefault("corner_radius", 8)
        kw.setdefault("height", 34)
        kw.setdefault("font", ctk.CTkFont(size=13))
        super().__init__(master, **kw)


class StatusBadge(ctk.CTkLabel):
    def __init__(self, master, **kw):
        kw.setdefault("fg_color", _CARD_TOP)
        kw.setdefault("corner_radius", 6)
        kw.setdefault("height", 24)
        kw.setdefault("font", ctk.CTkFont(size=11))
        super().__init__(master, **kw)

    def set_status(self, text: str, color: str = _TEXT_DIM) -> None:
        self.configure(text=f"  {text}  ", text_color=color)

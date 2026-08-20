import 'dart:convert';
import 'dart:io';
import 'dart:ffi';

import 'package:ffi/ffi.dart';
import 'package:flutter/foundation.dart';
import 'package:tray_manager/tray_manager.dart';
import 'package:win32/win32.dart';

/// Manages window-level features: always-on-top, persistent position/size,
/// minimize-to-tray, and system tray icon.
///
/// Uses the [win32] package to call native Windows API functions directly,
/// avoiding the window_manager plugin which is incompatible with Flutter 3.29+.
class WindowService extends ChangeNotifier {
  static WindowService? _instance;

  factory WindowService() => _instance ??= WindowService._internal();
  WindowService._internal();

  // ── State ─────────────────────────────────────────────────────────

  bool _alwaysOnTop = false;
  bool get alwaysOnTop => _alwaysOnTop;

  bool _minimizeToTray = true;
  bool get minimizeToTray => _minimizeToTray;

  bool _hasTray = false;
  bool get hasTray => _hasTray;

  bool _traySetupDone = false;

  /// Find the native window handle (HWND) by window title.
  /// Returns 0 if the window isn't found yet (e.g., during early startup).
  static int _findHwnd() {
    final title = 'VocalPro'.toNativeUtf16(allocator: calloc);
    try {
      return FindWindow(Pointer<Utf16>.fromAddress(0), title);
    } finally {
      calloc.free(title);
    }
  }

  // ── Init ──────────────────────────────────────────────────────────

  Future<void> init() async {
    _alwaysOnTop = await _loadAlwaysOnTopAsync();
    _minimizeToTray = await _loadMinimizeToTrayAsync();
    notifyListeners();
  }

  // ── Always-on-top ─────────────────────────────────────────────────

  Future<void> setAlwaysOnTop(bool value) async {
    _alwaysOnTop = value;
    final h = _findHwnd();
    if (h != 0) {
      SetWindowPos(h, value ? HWND_TOPMOST : HWND_NOTOPMOST, 0, 0, 0, 0,
          SWP_NOMOVE | SWP_NOSIZE);
    }
    await _saveAlwaysOnTopAsync(value);
    notifyListeners();
  }

  // ── Minimize to tray ──────────────────────────────────────────────

  Future<void> setMinimizeToTray(bool value) async {
    _minimizeToTray = value;
    await _saveMinimizeToTrayAsync(value);
    notifyListeners();
  }

  /// Handle window close/minimize event.
  /// Hides the window (minimize-to-tray) when tray is active;
  /// otherwise destroys the window which quits the app.
  Future<void> handleClose() async {
    final h = _findHwnd();
    if (h == 0) return;
    if (_minimizeToTray && _hasTray) {
      ShowWindow(h, SW_HIDE);
    } else {
      DestroyWindow(h);
    }
  }

  /// Restore window from tray.
  Future<void> showWindow() async {
    final h = _findHwnd();
    if (h == 0) return;
    ShowWindow(h, SW_SHOW);
    SetForegroundWindow(h);
  }

  // ── Tray ──────────────────────────────────────────────────────────

  Future<void> setupTray() async {
    if (_traySetupDone) return;
    _traySetupDone = true;

    try {
      final iconPath = await _getTrayIconPathAsync();
      if (iconPath == null) {
        _hasTray = false;
        return;
      }

      await TrayManager.instance.setIcon(iconPath);
      await TrayManager.instance.setToolTip('VocalPro');
      final menu = Menu(
        items: [
          MenuItem(
            key: 'show',
            label: 'Show VocalPro',
          ),
          MenuItem.separator(),
          MenuItem(
            key: 'quit',
            label: 'Quit',
          ),
        ],
      );
      await TrayManager.instance.setContextMenu(menu);
      _hasTray = true;
      notifyListeners();
    } catch (_) {
      _hasTray = false;
    }
  }

  // ── Persistent position ───────────────────────────────────────────

  Future<void> saveWindowPosition() async {
    try {
      final h = _findHwnd();
      if (h == 0) return;
      final rect = calloc<RECT>();
      GetWindowRect(h, rect);
      final data = {
        'x': rect.ref.left,
        'y': rect.ref.top,
        'width': rect.ref.right - rect.ref.left,
        'height': rect.ref.bottom - rect.ref.top,
      };
      calloc.free(rect);
      await _saveWindowDataAsync(data);
    } catch (_) {}
  }

  Future<void> loadWindowPosition() async {
    try {
      final data = await _loadWindowDataAsync();
      if (data == null) return;
      final h = _findHwnd();
      if (h == 0) return;
      SetWindowPos(
        h,
        0,
        (data['x'] as num).toInt(),
        (data['y'] as num).toInt(),
        (data['width'] as num).toInt(),
        (data['height'] as num).toInt(),
        SWP_NOZORDER,
      );
    } catch (_) {}
  }

  // ── Persistence helpers ───────────────────────────────────────────

  String _settingsFile() {
    final appData = Platform.environment['APPDATA'] ??
        Platform.environment['USERPROFILE'] ??
        Platform.environment['HOME'] ??
        '/tmp';
    return '$appData/VocalPro/window_settings.json';
  }

  Future<bool> _loadAlwaysOnTopAsync() async {
    try {
      final f = File(_settingsFile());
      if (!await f.exists()) return false;
      final data = jsonDecode(await f.readAsString()) as Map<String, dynamic>;
      return data['always_on_top'] as bool? ?? false;
    } catch (_) {
      return false;
    }
  }

  Future<void> _saveAlwaysOnTopAsync(bool value) async {
    await _mergeSettingAsync('always_on_top', value);
  }

  Future<bool> _loadMinimizeToTrayAsync() async {
    try {
      final f = File(_settingsFile());
      if (!await f.exists()) return true;
      final data = jsonDecode(await f.readAsString()) as Map<String, dynamic>;
      return data['minimize_to_tray'] as bool? ?? true;
    } catch (_) {
      return true;
    }
  }

  Future<void> _saveMinimizeToTrayAsync(bool value) async {
    await _mergeSettingAsync('minimize_to_tray', value);
  }

  Future<Map<String, dynamic>?> _loadWindowDataAsync() async {
    try {
      final f = File(_settingsFile());
      if (!await f.exists()) return null;
      final data = jsonDecode(await f.readAsString()) as Map<String, dynamic>;
      if (data['x'] == null ||
          data['y'] == null ||
          data['width'] == null ||
          data['height'] == null) {
        return null;
      }
      return data;
    } catch (_) {
      return null;
    }
  }

  Future<void> _saveWindowDataAsync(Map<String, dynamic> data) async {
    await _mergeSettingsAsync(data);
  }

  Future<void> _mergeSettingAsync(String key, dynamic value) async {
    await _mergeSettingsAsync({key: value});
  }

  Future<void> _mergeSettingsAsync(Map<String, dynamic> updates) async {
    try {
      final f = File(_settingsFile());
      final dir = f.parent;
      if (!await dir.exists()) await dir.create(recursive: true);

      Map<String, dynamic> settings = {};
      if (await f.exists()) {
        settings = jsonDecode(await f.readAsString()) as Map<String, dynamic>;
      }
      settings.addAll(updates);
      await f.writeAsString(jsonEncode(settings));
    } catch (_) {}
  }

  // ── Tray icon path ────────────────────────────────────────────────

  Future<String?> _getTrayIconPathAsync() async {
    // Use the app icon from the executable directory
    try {
      final exeDir = File(Platform.resolvedExecutable).parent.path;
      final icoPath = '$exeDir\\vocalpro.ico';
      if (await File(icoPath).exists()) return icoPath;
    } catch (_) {}

    // Fallback: no icon file found — can't set up tray
    return null;
  }

  // ── Dispose ───────────────────────────────────────────────────────

  @override
  void dispose() {
    _instance = null;
    super.dispose();
  }
}

/// Tray event listener — listens for tray icon clicks and menu selections.
class AppTrayListener extends TrayListener {
  @override
  void onTrayIconMouseDown() {
    WindowService().showWindow();
  }

  @override
  void onTrayMenuItemClick(MenuItem menuItem) {
    final winSvc = WindowService();
    switch (menuItem.key) {
      case 'show':
        winSvc.showWindow();
        break;
      case 'quit':
        final title = 'VocalPro'.toNativeUtf16(allocator: calloc);
        try {
          final h = FindWindow(Pointer<Utf16>.fromAddress(0), title);
          if (h != 0) DestroyWindow(h);
        } finally {
          calloc.free(title);
        }
        break;
    }
  }
}

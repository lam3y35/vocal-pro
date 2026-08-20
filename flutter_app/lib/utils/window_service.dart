import 'dart:convert';
import 'dart:io';
import 'dart:ui' show Offset, Size;

import 'package:flutter/foundation.dart';
import 'package:window_manager/window_manager.dart';
import 'package:tray_manager/tray_manager.dart';

/// Manages window-level features: always-on-top, persistent position/size,
/// minimize-to-tray, and system tray icon.
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

  // ── Init ──────────────────────────────────────────────────────────

  Future<void> init() async {
    _alwaysOnTop = _loadAlwaysOnTop();
    _minimizeToTray = _loadMinimizeToTray();
    notifyListeners();
  }

  // ── Always-on-top ─────────────────────────────────────────────────

  Future<void> setAlwaysOnTop(bool value) async {
    _alwaysOnTop = value;
    await WindowManager.instance.setAlwaysOnTop(value);
    _saveAlwaysOnTop(value);
    notifyListeners();
  }

  // ── Minimize to tray ──────────────────────────────────────────────

  Future<void> setMinimizeToTray(bool value) async {
    _minimizeToTray = value;
    _saveMinimizeToTray(value);
    notifyListeners();
  }

  /// Handle window close/minimize event.
  Future<void> handleClose() async {
    if (_minimizeToTray && _hasTray) {
      await WindowManager.instance.hide();
    } else {
      await WindowManager.instance.close();
    }
  }

  /// Restore window from tray.
  Future<void> showWindow() async {
    await WindowManager.instance.show();
    await WindowManager.instance.focus();
  }

  // ── Tray ──────────────────────────────────────────────────────────

  Future<void> setupTray() async {
    if (_traySetupDone) return;
    _traySetupDone = true;

    try {
      final iconPath = _getTrayIconPath();
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
      final pos = await WindowManager.instance.getPosition();
      final size = await WindowManager.instance.getSize();
      final data = {
        'x': pos.dx,
        'y': pos.dy,
        'width': size.width,
        'height': size.height,
      };
      _saveWindowData(data);
    } catch (_) {}
  }

  Future<void> loadWindowPosition() async {
    try {
      final data = _loadWindowData();
      if (data == null) return;
      await WindowManager.instance.setPosition(
        Offset(data['x'] as double, data['y'] as double),
      );
      await WindowManager.instance.setSize(
        Size(data['width'] as double, data['height'] as double),
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

  bool _loadAlwaysOnTop() {
    try {
      final f = File(_settingsFile());
      if (!f.existsSync()) return false;
      final data = jsonDecode(f.readAsStringSync()) as Map<String, dynamic>;
      return data['always_on_top'] as bool? ?? false;
    } catch (_) {
      return false;
    }
  }

  void _saveAlwaysOnTop(bool value) {
    _mergeSetting('always_on_top', value);
  }

  bool _loadMinimizeToTray() {
    try {
      final f = File(_settingsFile());
      if (!f.existsSync()) return true;
      final data = jsonDecode(f.readAsStringSync()) as Map<String, dynamic>;
      return data['minimize_to_tray'] as bool? ?? true;
    } catch (_) {
      return true;
    }
  }

  void _saveMinimizeToTray(bool value) {
    _mergeSetting('minimize_to_tray', value);
  }

  Map<String, dynamic>? _loadWindowData() {
    try {
      final f = File(_settingsFile());
      if (!f.existsSync()) return null;
      final data = jsonDecode(f.readAsStringSync()) as Map<String, dynamic>;
      if (data['x'] == null || data['y'] == null || data['width'] == null || data['height'] == null) return null;
      return data;
    } catch (_) {
      return null;
    }
  }

  void _saveWindowData(Map<String, dynamic> data) {
    _mergeSettings(data);
  }

  void _mergeSetting(String key, dynamic value) {
    _mergeSettings({key: value});
  }

  void _mergeSettings(Map<String, dynamic> updates) {
    try {
      final f = File(_settingsFile());
      final dir = f.parent;
      if (!dir.existsSync()) dir.createSync(recursive: true);

      Map<String, dynamic> settings = {};
      if (f.existsSync()) {
        settings = jsonDecode(f.readAsStringSync()) as Map<String, dynamic>;
      }
      settings.addAll(updates);
      f.writeAsStringSync(jsonEncode(settings));
    } catch (_) {}
  }

  // ── Tray icon path ────────────────────────────────────────────────

  String? _getTrayIconPath() {
    // Use the app icon from the executable directory
    try {
      final exeDir = File(Platform.resolvedExecutable).parent.path;
      final icoPath = '$exeDir\\vocalpro.ico';
      if (File(icoPath).existsSync()) return icoPath;
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
}/// Tray event listener — listens for tray icon clicks and menu selections.
class AppTrayListener extends TrayListener {
  @override
  void onTrayIconMouseDown() {
    WindowService().showWindow();
  }

  @override
  void onTrayMenuItemClick(MenuItem menuItem) {
    switch (menuItem.key) {
      case 'show':
        WindowService().showWindow();
        break;
      case 'quit':
        WindowManager.instance.destroy();
        break;
    }
  }
}



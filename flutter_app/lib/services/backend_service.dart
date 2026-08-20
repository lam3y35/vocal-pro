import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

/// Manages the Python API server child process lifecycle.
///
/// Design:
/// 1. On [start], first checks if port 8000 already responds (quick HTTP GET
///    to /api/health with 500ms timeout). If yes — skip spawning (user may
///    already have the server running manually).
/// 2. If no server is detected, locates Python on PATH (or uses a custom path
///    from local settings) and spawns `run_server.py` as a child process.
/// 3. Polls the health endpoint every 500ms until the server responds or a
///    deadline elapses.
/// 4. [stop] / [dispose] kills the child process.
class BackendService {
  final String baseUrl;
  Process? _process;
  bool _started = false;
  bool _startAttempted = false;
  String? _pythonPathOverride;

  BackendService({this.baseUrl = 'http://127.0.0.1:8000'}) {
    _pythonPathOverride = _loadPythonPath();
  }

  // ── State queries ─────────────────────────────────────────────────

  /// Whether the server has been confirmed running at least once.
  bool get isRunning => _started;

  /// Whether a start attempt has been made (for UI state).
  bool get startAttempted => _startAttempted;

  /// The custom Python path, or null to use PATH detection.
  String? get pythonPathOverride => _pythonPathOverride;

  // ── Start / stop ──────────────────────────────────────────────────

  /// Start (or detect) the backend server.
  ///
  /// Returns `true` if the server is responding after this call.
  /// Fires [onStatusChanged] as internal state progresses.
  Future<bool> start({
    Duration healthTimeout = const Duration(milliseconds: 500),
    Duration maxWait = const Duration(seconds: 40),
  }) async {
    _startAttempted = true;

    // 1. Quick health check — skip spawning if already running.
    if (await _checkHealth(timeout: healthTimeout)) {
      _started = true;
      return true;
    }

    // 2. Find the Python executable.
    final pythonExe = _resolvePython();
    if (pythonExe == null) {
      return false;
    }

    // 3. Find the server script.
    final scriptPath = _findServerScript();
    if (scriptPath == null) {
      return false;
    }

    // 4. Spawn the child process.
    try {
      final workingDir = File(scriptPath).parent.path;
      _process = await Process.start(
        pythonExe,
        [scriptPath],
        workingDirectory: workingDir,
        runInShell: true,
      );

      // Drain stdout / stderr to prevent deadlocks.
      _process!.stdout.transform(utf8.decoder).listen((_) {});
      _process!.stderr.transform(utf8.decoder).listen((_) {});

      // 5. Poll for health.
      final deadline = DateTime.now().add(maxWait);
      while (DateTime.now().isBefore(deadline)) {
        await Future.delayed(const Duration(milliseconds: 500));
        if (await _checkHealth(timeout: const Duration(seconds: 2))) {
          _started = true;
          return true;
        }
      }

      // Timed out — kill the hung process.
      _process?.kill();
      _process = null;
      return false;
    } catch (_) {
      _process?.kill();
      _process = null;
      return false;
    }
  }

  /// Kill the child process if one was spawned.
  Future<void> stop() async {
    _process?.kill();
    _process = null;
    _started = false;
  }

  /// Quick health check.
  Future<bool> _checkHealth({Duration timeout = const Duration(milliseconds: 500)}) async {
    try {
      final resp = await http
          .get(Uri.parse('$baseUrl/api/health'))
          .timeout(timeout);
      return resp.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// Health check exposed for the HomeScreen dashboard.
  Future<Map<String, dynamic>> health() async {
    try {
      final resp = await http
          .get(Uri.parse('$baseUrl/api/health'))
          .timeout(const Duration(seconds: 3));
      if (resp.statusCode == 200) {
        return jsonDecode(resp.body) as Map<String, dynamic>;
      }
      return {'status': 'offline', 'error': 'HTTP ${resp.statusCode}'};
    } catch (e) {
      return {'status': 'offline', 'error': e.toString()};
    }
  }

  // ── Python path resolution ────────────────────────────────────────

  /// Resolve the Python executable path.
  ///
  /// Priority:
  /// 1. User override from local settings
  /// 2. `python` on PATH
  /// 3. `python3` on PATH
  String? _resolvePython() {
    if (_pythonPathOverride != null && _pythonPathOverride!.isNotEmpty) {
      // Check if the override exists.
      if (File(_pythonPathOverride!).existsSync()) return _pythonPathOverride;
      // It might be a command name (e.g. "python"), return as-is.
      return _pythonPathOverride;
    }
    // Try common names.
    for (final name in ['python', 'python3']) {
      try {
        final result = Process.runSync(name, ['--version']);
        if (result.exitCode == 0) return name;
      } catch (_) {}
    }
    return null;
  }

  /// Set a custom Python path and persist it locally.
  void setPythonPath(String path) {
    _pythonPathOverride = path;
    _savePythonPath(path);
  }

  // ── Server script discovery ───────────────────────────────────────

  /// Locate `run_server.py` relative to the app.
  String? _findServerScript() {
    final cwd = Directory.current.path;

    // Check common locations relative to cwd
    final candidates = [
      '$cwd/api_server/run_server.py',
      '$cwd/api_server/main.py',
      // Flutter app dir → project root
      '${_parentOf(cwd, 1)}/api_server/run_server.py',
      '${_parentOf(cwd, 1)}/api_server/main.py',
      // Windows: running from flutter_app/
      '$cwd/../api_server/run_server.py',
      '$cwd/../api_server/main.py',
    ];

    for (final path in candidates) {
      final normalized = path.replaceAll('/', Platform.pathSeparator);
      if (File(normalized).existsSync()) return normalized;
    }

    // Try relative to the executable
    try {
      final exeDir = Directory(Platform.resolvedExecutable).parent.path;
      final exeCandidates = [
        '$exeDir/api_server/run_server.py',
        '$exeDir/api_server/main.py',
        '${_parentOf(exeDir, 1)}/api_server/run_server.py',
        '${_parentOf(exeDir, 1)}/api_server/main.py',
      ];
      for (final path in exeCandidates) {
        if (File(path).existsSync()) return path;
      }
    } catch (_) {}

    return null;
  }

  static String _parentOf(String dir, int levels) {
    var result = dir;
    for (int i = 0; i < levels; i++) {
      result = Directory(result).parent.path;
    }
    return result;
  }

  // ── Local persistence (for settings that must exist pre-server) ──

  static String _settingsFilePath() {
    final appData = Platform.environment['APPDATA'] ??
        Platform.environment['USERPROFILE'] ??
        Platform.environment['HOME'] ??
        '/tmp';
    return '$appData/VocalPro/flutter_settings.json';
  }

  void _savePythonPath(String path) {
    try {
      final filePath = _settingsFilePath();
      final dir = Directory(filePath).parent;
      if (!dir.existsSync()) dir.createSync(recursive: true);

      // Merge with existing settings.
      Map<String, dynamic> settings = {};
      final existing = File(filePath);
      if (existing.existsSync()) {
        settings = jsonDecode(existing.readAsStringSync()) as Map<String, dynamic>;
      }
      settings['python_path'] = path;
      existing.writeAsStringSync(jsonEncode(settings));
    } catch (_) {}
  }

  String? _loadPythonPath() {
    try {
      final filePath = _settingsFilePath();
      final file = File(filePath);
      if (file.existsSync()) {
        final data = jsonDecode(file.readAsStringSync()) as Map<String, dynamic>;
        return data['python_path'] as String?;
      }
    } catch (_) {}
    return null;
  }

  // ── Lifecycle ─────────────────────────────────────────────────────

  void dispose() {
    stop();
  }
}

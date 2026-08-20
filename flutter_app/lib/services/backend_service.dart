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
  String? _lastError;
  http.Client? _httpClient;

  /// Shared HTTP client for connection pooling.
  /// Reuses connections across health checks instead of creating a new
  /// TCP socket per request — prevents TIME_WAIT socket accumulation
  /// on Windows when the server is unreachable.
  http.Client get _client => _httpClient ??= http.Client();

  /// Human-readable error from the last start() attempt.
  String? get lastError => _lastError;

  BackendService({this.baseUrl = 'http://127.0.0.1:8000'}) {
    // _pythonPathOverride loaded lazily on first start() call
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
  /// Design notes on socket management:
  /// - Uses a shared [http.Client] for all health checks so that TCP
  ///   connections are properly pooled and closed, preventing the
  ///   accumulation of TIME_WAIT sockets on Windows.
  /// - Polls every 2 seconds (not 500ms) to reduce connection churn.
  /// - Waits 3 seconds before the first health check to let the system
  ///   recover from previous connection attempts.
  ///
  /// Returns `true` if the server is responding after this call.
  Future<bool> start({
    Duration healthTimeout = const Duration(seconds: 2),
    Duration maxWait = const Duration(seconds: 30),
  }) async {
    _startAttempted = true;

    // 0. Brief delay before any health checks — lets the TCP stack
    //    recover if the system is recovering from socket exhaustion.
    await Future.delayed(const Duration(seconds: 3));

    // 1. Quick health check — skip spawning if already running.
    if (await _checkHealth(timeout: healthTimeout)) {
      _started = true;
      return true;
    }

    // 2. Load saved Python path override if not already loaded.
    _pythonPathOverride ??= await _loadPythonPathAsync();

    // 3. Find the Python executable (async).
    final pythonExe = await _resolvePythonAsync();
    if (pythonExe == null) {
      _lastError = 'Python not found. Make sure Python 3.12+ is installed and on PATH, or set a custom path in Settings.';
      return false;
    }

    // 4. Find the server script (async).
    final scriptPath = await _findServerScriptAsync();
    if (scriptPath == null) {
      _lastError = 'Server script (api_server/main.py) not found. The app may be installed incorrectly.';
      return false;
    }

    // 5. Spawn the child process.
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

      // 6. Poll for health every 2 seconds.
      //    Note: 2s interval (not 500ms) to avoid flooding the TCP
      //    stack with connections when the server is slow to start.
      final deadline = DateTime.now().add(maxWait);
      while (DateTime.now().isBefore(deadline)) {
        await Future.delayed(const Duration(seconds: 2));
        if (await _checkHealth(timeout: const Duration(seconds: 4))) {
          _started = true;
          return true;
        }
      }
    } catch (e) {
      _lastError = 'Failed to start server process: $e';
      _process?.kill();
      _process = null;
      return false;
    }

    // Timed out (health check loop exited without returning) — kill the hung process.
    _process?.kill();
    _process = null;
    _lastError = 'Server failed to start within $maxWait. Check if port 8000 is in use or Python dependencies are missing.';
    return false;
  }

  /// Retry starting the server (calls start() again, clearing any previous error).
  Future<bool> retry({Duration maxWait = const Duration(seconds: 40)}) async {
    _lastError = null;
    _startAttempted = false;
    return start(maxWait: maxWait);
  }

  /// Kill the child process if one was spawned.
  Future<void> stop() async {
    _process?.kill();
    _process = null;
    _started = false;
  }

  /// Quick health check using the shared client.
  /// Uses a 2-second timeout so the socket isn't held open long when the
  /// server is unreachable.
  Future<bool> _checkHealth({Duration timeout = const Duration(seconds: 2)}) async {
    final client = _client;
    try {
      final resp = await client
          .get(Uri.parse('$baseUrl/api/health'))
          .timeout(timeout);
      return resp.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  /// Health check exposed for the HomeScreen dashboard.
  Future<Map<String, dynamic>> health() async {
    final client = _client;
    try {
      final resp = await client
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

  /// Resolve the Python executable path (async — does not block UI thread).
  ///
  /// Priority:
  /// 1. User override from local settings
  /// 2. Project venv (relative to app exe or cwd)
  /// 3. `python` on PATH
  /// 4. `python3` on PATH
  Future<String?> _resolvePythonAsync() async {
    if (_pythonPathOverride != null && _pythonPathOverride!.isNotEmpty) {
      if (await File(_pythonPathOverride!).exists()) return _pythonPathOverride;
      return _pythonPathOverride;
    }

    // Check for project virtual environment (venv) relative to the exe or cwd
    final venvCandidates = [
      // Relative to the Flutter exe (release build)
      '${_parentOf(Platform.resolvedExecutable, 1)}/venv/Scripts/python.exe',
      '${_parentOf(Platform.resolvedExecutable, 2)}/venv/Scripts/python.exe',
      // Relative to project root via cwd
      '${Directory.current.path}/../venv/Scripts/python.exe',
      '${Directory.current.path}/venv/Scripts/python.exe',
      // Windows paths with backslashes
      '${_parentOf(Platform.resolvedExecutable, 1)}\\venv\\Scripts\\python.exe',
      '${_parentOf(Platform.resolvedExecutable, 2)}\\venv\\Scripts\\python.exe',
    ];

    for (final candidate in venvCandidates) {
      try {
        if (await File(candidate).exists()) return candidate;
      } catch (_) {}
    }

    // Try common names on PATH (async so UI thread is free).
    for (final name in ['python', 'python3']) {
      try {
        final result = await Process.run(name, ['--version']);
        if (result.exitCode == 0) return name;
      } catch (_) {}
    }
    return null;
  }

  /// Set a custom Python path and persist it locally (async).
  Future<void> setPythonPath(String path) async {
    _pythonPathOverride = path;
    await _savePythonPathAsync(path);
  }

  // ── Server script discovery ───────────────────────────────────────

  /// Locate `run_server.py` relative to the app (async — does not block UI thread).
  Future<String?> _findServerScriptAsync() async {
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
      if (await File(normalized).exists()) return normalized;
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
        if (await File(path).exists()) return path;
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

  Future<void> _savePythonPathAsync(String path) async {
    try {
      final filePath = _settingsFilePath();
      final dir = Directory(filePath).parent;
      if (!await dir.exists()) await dir.create(recursive: true);

      // Merge with existing settings.
      Map<String, dynamic> settings = {};
      final existing = File(filePath);
      if (await existing.exists()) {
        settings = jsonDecode(await existing.readAsString()) as Map<String, dynamic>;
      }
      settings['python_path'] = path;
      await existing.writeAsString(jsonEncode(settings));
    } catch (_) {}
  }

  Future<String?> _loadPythonPathAsync() async {
    try {
      final filePath = _settingsFilePath();
      final file = File(filePath);
      if (await file.exists()) {
        final data = jsonDecode(await file.readAsString()) as Map<String, dynamic>;
        return data['python_path'] as String?;
      }
    } catch (_) {}
    return null;
  }

  // ── Lifecycle ─────────────────────────────────────────────────────

  void dispose() {
    _httpClient?.close();
    _httpClient = null;
    stop();
  }
}

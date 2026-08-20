import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:web_socket_channel/web_socket_channel.dart';

/// VocalPro API client – HTTP + WebSocket for real-time progress.
class ApiService {
  final String baseUrl;
  final String wsUrl;
  final http.Client _client = http.Client();

  ApiService({
    this.baseUrl = 'http://127.0.0.1:8000',
    String? wsUrl,
  }) : wsUrl = wsUrl ?? 'ws://127.0.0.1:8000/ws/progress';

  // ── Health ────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> health() async {
    final resp = await _client.get(Uri.parse('$baseUrl/api/health'));
    return jsonDecode(resp.body);
  }

  // ── Config ────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> getConfig() async {
    final resp = await _client.get(Uri.parse('$baseUrl/api/config'));
    return jsonDecode(resp.body);
  }

  Future<Map<String, dynamic>> getDefaults() async {
    final resp = await _client.get(Uri.parse('$baseUrl/api/config/defaults'));
    return jsonDecode(resp.body);
  }

  Future<void> updateConfig(String key, dynamic value) async {
    await _client.post(
      Uri.parse('$baseUrl/api/config'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode([{'key': key, 'value': value}]),
    );
  }

  Future<void> updateConfigs(List<Map<String, dynamic>> updates) async {
    await _client.post(
      Uri.parse('$baseUrl/api/config'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(updates),
    );
  }

  // ── Models ────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> getModels() async {
    final resp = await _client.get(Uri.parse('$baseUrl/api/models'));
    return jsonDecode(resp.body);
  }

  // ── Upload ────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> uploadFile(String filePath) async {
    final request = http.MultipartRequest('POST', Uri.parse('$baseUrl/api/upload'));
    final file = await http.MultipartFile.fromPath('file', filePath);
    request.files.add(file);
    final streamed = await _client.send(request);
    final resp = await http.Response.fromStream(streamed);
    return jsonDecode(resp.body);
  }

  // ── Download URL ──────────────────────────────────────────────────

  Future<Map<String, dynamic>> downloadUrl(String url) async {
    final resp = await _client.post(
      Uri.parse('$baseUrl/api/download'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'url': url}),
    );
    return jsonDecode(resp.body);
  }

  // ── Audio Analysis (BPM, key, waveform) ───────────────────────────

  Future<Map<String, dynamic>> analyzeAudio(String filePath) async {
    final resp = await _client.post(
      Uri.parse('$baseUrl/api/analyze'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'file_path': filePath}),
    );
    return jsonDecode(resp.body);
  }

  // ── Separation (multi-job) ───────────────────────────────────────────

  Future<Map<String, dynamic>> startSeparation({
    required List<String> filePaths,
    String? outputDir,
    String modelName = 'htdemucs',
    String outputFormat = 'wav',
    bool enableGate = true,
    bool enableDenoise = true,
    bool enableMultiband = false,
    bool enableProfile = false,
    bool adaptiveGate = false,
    bool trimSilence = false,
    bool karaokeMode = false,
    bool ensembleMode = false,
    bool includeSfx = true,
    bool saveBg = false,
    bool genSamples = false,
    bool enableSfxSep = false,
    double segment = 6.0,
    double overlap = 2.0,
    int shifts = 1,
    double gateThresholdDb = -55.0,
    double gateFloorDb = -60.0,
    double denoiseStrength = 0.55,
    double minVocalDuration = 0.08,
    String videoOutputMode = 'both',
    int parallelWorkers = 1,
  }) async {
    final resp = await _client.post(
      Uri.parse('$baseUrl/api/separate'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'file_paths': filePaths,
        'output_dir': outputDir,
        'model_name': modelName,
        'output_format': outputFormat,
        'parallel_workers': parallelWorkers,
        'enable_vocal_gate': enableGate,
        'enable_spectral_denoise': enableDenoise,
        'enable_multiband_denoise': enableMultiband,
        'enable_noise_profile': enableProfile,
        'adaptive_gate_floor': adaptiveGate,
        'trim_silence': trimSilence,
        'karaoke_mode': karaokeMode,
        'ensemble_mode': ensembleMode,
        'include_sfx': includeSfx,
        'save_background_track': saveBg,
        'generate_comparison_samples': genSamples,
        'enable_sfx_separation': enableSfxSep,
        'segment': segment,
        'overlap': overlap,
        'shifts': shifts,
        'gate_threshold_db': gateThresholdDb,
        'gate_floor_db': gateFloorDb,
        'denoise_strength': denoiseStrength,
        'min_vocal_duration': minVocalDuration,
        'video_output_mode': videoOutputMode,
      }),
    ).timeout(const Duration(seconds: 30));
    return jsonDecode(resp.body);
  }

  /// List all jobs from the backend.
  Future<List<Map<String, dynamic>>> listJobs() async {
    final resp = await _client.get(Uri.parse('$baseUrl/api/jobs'));
    final data = jsonDecode(resp.body);
    return (data['jobs'] as List<dynamic>?)?.cast<Map<String, dynamic>>() ?? [];
  }

  /// Get details of a specific job.
  Future<Map<String, dynamic>> getJob(String jobId) async {
    final resp = await _client.get(Uri.parse('$baseUrl/api/jobs/$jobId'));
    final data = jsonDecode(resp.body);
    return data['job'] as Map<String, dynamic>? ?? {};
  }

  /// Cancel a specific job.
  Future<void> cancelJob(String jobId) async {
    await _client.post(Uri.parse('$baseUrl/api/jobs/$jobId/cancel'));
  }

  /// Cancel the most recent running job (backward compat).
  Future<void> cancelSeparation() async {
    await _client.post(Uri.parse('$baseUrl/api/cancel'));
  }

  Future<Map<String, dynamic>> getStatus() async {
    final resp = await _client.get(Uri.parse('$baseUrl/api/status'));
    return jsonDecode(resp.body);
  }

  // ── History ───────────────────────────────────────────────────────

  Future<Map<String, dynamic>> getHistory() async {
    final resp = await _client.get(Uri.parse('$baseUrl/api/history'));
    return jsonDecode(resp.body);
  }

  Future<Map<String, dynamic>> getDownloadHistory() async {
    final resp = await _client.get(Uri.parse('$baseUrl/api/download_history'));
    return jsonDecode(resp.body);
  }

  Future<void> clearSepHistory() async {
    await _client.delete(Uri.parse('$baseUrl/api/history'));
  }

  Future<void> clearDownloadHistory() async {
    await _client.delete(Uri.parse('$baseUrl/api/download_history'));
  }

  // ── Rerun ─────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> rerunSeparation({
    required List<String> filePaths,
    String? outputDir,
    String modelName = 'htdemucs',
    String outputFormat = 'wav',
    bool enableGate = true,
    bool enableDenoise = true,
    bool enableMultiband = false,
    bool enableProfile = false,
    bool adaptiveGate = false,
    bool trimSilence = false,
    bool karaokeMode = false,
    bool ensembleMode = false,
    bool includeSfx = true,
    bool saveBg = false,
    bool genSamples = false,
    bool enableSfxSep = true,
  }) async {
    return startSeparation(
      filePaths: filePaths,
      outputDir: outputDir,
      modelName: modelName,
      outputFormat: outputFormat,
      enableGate: enableGate,
      enableDenoise: enableDenoise,
      enableMultiband: enableMultiband,
      enableProfile: enableProfile,
      adaptiveGate: adaptiveGate,
      trimSilence: trimSilence,
      karaokeMode: karaokeMode,
      ensembleMode: ensembleMode,
      includeSfx: includeSfx,
      saveBg: saveBg,
      genSamples: genSamples,
      enableSfxSep: enableSfxSep,
    );
  }

  // ── Outputs ───────────────────────────────────────────────────────

  Future<Map<String, dynamic>> getOutputs() async {
    final resp = await _client.get(Uri.parse('$baseUrl/api/outputs'));
    return jsonDecode(resp.body);
  }

  Future<Map<String, dynamic>> getStems(String folderName) async {
    final resp = await _client.get(Uri.parse('$baseUrl/api/outputs/$folderName/stems'));
    return jsonDecode(resp.body);
  }

  String getDownloadUrl(String folderName, String fileName) {
    return '$baseUrl/api/outputs/$folderName/$fileName';
  }

  // ── Stem Mixer ────────────────────────────────────────────────────

  Future<List<int>> stemPreview({
    required String folderName,
    Map<String, double> volumes = const {},
    double masterVolume = 1.0,
  }) async {
    final resp = await _client.post(
      Uri.parse('$baseUrl/api/stems/preview'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'folder_name': folderName,
        'volumes': volumes,
        'master_volume': masterVolume,
      }),
    );
    return resp.bodyBytes.toList();
  }

  Future<Map<String, dynamic>> stemExport({
    required String folderName,
    Map<String, double> volumes = const {},
    double masterVolume = 1.0,
    String outputFormat = 'wav',
  }) async {
    final resp = await _client.post(
      Uri.parse('$baseUrl/api/stems/export'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'folder_name': folderName,
        'volumes': volumes,
        'master_volume': masterVolume,
        'output_format': outputFormat,
      }),
    );
    return jsonDecode(resp.body);
  }

  Future<Map<String, dynamic>> stemExportSeparate({
    required String folderName,
    Map<String, double> volumes = const {},
    double masterVolume = 1.0,
    String outputFormat = 'wav',
  }) async {
    final resp = await _client.post(
      Uri.parse('$baseUrl/api/stems/export_separate'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'folder_name': folderName,
        'volumes': volumes,
        'master_volume': masterVolume,
        'output_format': outputFormat,
      }),
    );
    return jsonDecode(resp.body);
  }

  Future<Map<String, dynamic>> stemToMidi(String filePath) async {
    final resp = await _client.post(
      Uri.parse('$baseUrl/api/stems/midi'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'file_path': filePath}),
    );
    return jsonDecode(resp.body);
  }

  // ── WebSocket ─────────────────────────────────────────────────────

  WebSocketChannel? _channel;
  Timer? _pingTimer;
  Timer? _reconnectTimer;
  bool _hasConnectedOnce = false;
  bool _intentionalDisconnect = false;
  final _eventController = StreamController<ProgressEvent>.broadcast();
  Stream<ProgressEvent> get onProgress => _eventController.stream;

  // Connection state tracking
  WsConnectionState _wsState = WsConnectionState.disconnected;
  WsConnectionState get wsState => _wsState;

  // Exponential backoff: starts at 1s, doubles each retry, caps at 30s
  int _reconnectAttempts = 0;
  static const _initialBackoff = Duration(seconds: 1);
  static const _maxBackoff = Duration(seconds: 30);
  static const _maxReconnectAttempts = 50; // after this, stop trying
  static const _backoffResetAfter = Duration(minutes: 2);
  DateTime? _lastSuccessfulConnect;

  Duration _getBackoffDelay() {
    // Reset backoff if we were connected for a while (server probably
    // restarted normally, not a crash loop).
    if (_lastSuccessfulConnect != null &&
        DateTime.now().difference(_lastSuccessfulConnect!) > _backoffResetAfter) {
      _reconnectAttempts = 0;
    }
    final delay = Duration(
      seconds: (1 << _reconnectAttempts.clamp(0, 4)).clamp(
        _initialBackoff.inSeconds,
        _maxBackoff.inSeconds,
      ),
    );
    _reconnectAttempts++;
    return delay;
  }

  void connectWebSocket() {
    // Don't reconnect if intentionally disconnected or at retry limit
    if (_intentionalDisconnect) return;
    if (_reconnectAttempts >= _maxReconnectAttempts) {
      _eventController.add(ProgressEvent(
        type: ProgressType.error,
        message: 'WebSocket gave up reconnecting after $_maxReconnectAttempts attempts',
      ));
      return;
    }

    // Cancel any pending reconnect to avoid duplicate connections
    _reconnectTimer?.cancel();
    _reconnectTimer = null;

    // ── Clean up any previous connection first ──────────────────────
    _pingTimer?.cancel();
    _pingTimer = null;
    _safeCloseChannel();
    _channel = null;
    _wsState = WsConnectionState.connecting;

    try {
      _channel = WebSocketChannel.connect(Uri.parse(wsUrl));
      _channel!.stream.listen(
        (data) {
          // Any data means the connection is alive
          if (_wsState != WsConnectionState.connected) {
            _wsState = WsConnectionState.connected;
            _reconnectAttempts = 0; // Reset backoff on successful connect
            _lastSuccessfulConnect = DateTime.now();
          }
          final msg = jsonDecode(data);
          _eventController.add(ProgressEvent.fromJson(msg));
        },
        onError: (error) {
          _scheduleReconnect();
        },
        onDone: () {
          _scheduleReconnect();
        },
      );

      // Emit a "reconnected" event ONLY on reconnections (not the first
      // connect) so controllers can detect server restarts and recover
      // from stale state (e.g. stuck at "Initializing...").
      if (_hasConnectedOnce) {
        _wsState = WsConnectionState.reconnecting;
        _eventController.add(ProgressEvent(
          type: ProgressType.reconnected,
        ));
      }
      _hasConnectedOnce = true;

      _pingTimer = Timer.periodic(const Duration(seconds: 15), (_) {
        try {
          _channel?.sink.add('ping');
        } catch (_) {
          _scheduleReconnect();
        }
      });
    } catch (_) {
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    if (_intentionalDisconnect) return;
    _wsState = WsConnectionState.disconnected;
    _pingTimer?.cancel();
    _pingTimer = null;
    _safeCloseChannel();
    _channel = null;

    final delay = _getBackoffDelay();
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(delay, connectWebSocket);
  }

  void _safeCloseChannel() {
    try {
      _channel?.sink.close();
    } catch (_) {}
  }

  void disconnectWebSocket() {
    _intentionalDisconnect = true;
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
    _pingTimer?.cancel();
    _pingTimer = null;
    _safeCloseChannel();
    _channel = null;
    _wsState = WsConnectionState.disconnected;
    _reconnectAttempts = 0;
  }

  /// Re-enable reconnection (e.g. after a user-initiated retry).
  void enableReconnection() {
    _intentionalDisconnect = false;
    _reconnectAttempts = 0;
  }

  void dispose() {
    _hasConnectedOnce = false;
    _intentionalDisconnect = true;
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
    disconnectWebSocket();
    _eventController.close();
    _client.close();
  }
}

// ── Progress event model ─────────────────────────────────────────────

enum ProgressType { progress, fileStart, done, error, cancelled, pong, reconnected }

/// WebSocket connection state for UI display.
enum WsConnectionState { disconnected, connecting, connected, reconnecting }

class ProgressEvent {
  final ProgressType type;
  final double? percent;
  final String? message;
  final String? outputPath;
  final int? index;
  final int? total;
  final String? filename;
  final String? jobId;

  ProgressEvent({
    required this.type,
    this.percent,
    this.message,
    this.outputPath,
    this.index,
    this.total,
    this.filename,
    this.jobId,
  });

  factory ProgressEvent.fromJson(Map<String, dynamic> json) {
    return ProgressEvent(
      type: _parseType(json['type']),
      percent: (json['percent'] as num?)?.toDouble(),
      message: json['message'] as String?,
      outputPath: json['output_path'] as String?,
      index: json['index'] as int?,
      total: json['total'] as int?,
      filename: json['filename'] as String?,
      jobId: json['job_id'] as String?,
    );
  }

  static ProgressType _parseType(String? t) {
    switch (t) {
      case 'progress':
        return ProgressType.progress;
      case 'file_start':
        return ProgressType.fileStart;
      case 'done':
        return ProgressType.done;
      case 'error':
        return ProgressType.error;
      case 'cancelled':
        return ProgressType.cancelled;
      case 'pong':
        return ProgressType.pong;
      case 'reconnected':
        return ProgressType.reconnected;
      default:
        return ProgressType.progress;
    }
  }
}

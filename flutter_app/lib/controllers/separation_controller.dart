import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:file_picker/file_picker.dart';
import 'package:audioplayers/audioplayers.dart';
import 'package:open_filex/open_filex.dart';
import '../services/api_service.dart';
import '../l10n/app_localizations.dart';
import '../theme.dart';
import '../widgets/cards.dart';
import '../widgets/separation/shared.dart';

/// Controller for the Separation screen — owns all state and business logic.
/// Injected into sub-widgets so they can read / mutate state without
/// each widget needing its own StatefulWidget.
class SeparationController extends ChangeNotifier {
  final ApiService api;
  // Callback fired when separation completes successfully (passes output path)
  void Function(String? outputPath)? onSeparationComplete;
  // Callback fired when Ctrl+R is pressed — wired to start a new job via JobManager
  VoidCallback? onStartNewJob;

  SeparationController({required this.api, AppLocalizations? l10n})
      : _statusText = l10n?.readyLog ?? 'Ready' {
    _wsSub = api.onProgress.listen(_onProgressEvent);
  }

  // ── Throttle: limit UI rebuilds during rapid progress updates ──
  DateTime _lastProgressNotify = DateTime.fromMillisecondsSinceEpoch(0);
  static const _progressNotifyInterval = Duration(milliseconds: 100);

  /// Call notifyListeners() but throttle during progress updates to avoid
  /// rebuilding the entire widget tree on every WebSocket message (~10/sec).
  void _throttledNotify() {
    final now = DateTime.now();
    if (now.difference(_lastProgressNotify) >= _progressNotifyInterval) {
      _lastProgressNotify = now;
      notifyListeners();
    }
  }

  // ── Server connectivity ──────────────────────────────────────────────────

  bool _serverOffline = false;
  /// Whether the last error was a server connection failure (for UI retry button).
  bool get serverOffline => _serverOffline;

  /// Check if the backend server is reachable by calling /api/health.
  /// Returns `true` if the server is online, `false` otherwise.
  /// Sets [_serverOffline] based on the result.
  Future<bool> checkServerOnline() async {
    try {
      final resp = await api.health();
      _serverOffline = resp['status'] != 'ok';
      return !_serverOffline;
    } catch (_) {
      _serverOffline = true;
      return false;
    }
  }

  /// Reset the server offline flag (after a successful retry).
  void markServerOnline() {
    _serverOffline = false;
    notifyListeners();
  }

  // ── Lifecycle ──────────────────────────────────────────────────────────

  bool _disposed = false;
  StreamSubscription<ProgressEvent>? _wsSub;

  @override
  void dispose() {
    _disposed = true;
    _wsSub?.cancel();
    _playbackTimer?.cancel();
    _workflowTimer?.cancel();
    _pollTimer?.cancel();
    _urlController.dispose();
    _outputDirController.dispose();
    _audioPlayer.dispose();
    super.dispose();
  }

  // ── Files ──────────────────────────────────────────────────────────────

  final List<QueuedFile> _files = [];
  List<QueuedFile> get files => _files;
  int get fileCount => _files.length;

  void addFiles(List<PlatformFile> platformFiles) {
    for (final pf in platformFiles) {
      if (pf.path != null && !_files.any((q) => q.path == pf.path)) {
        _files.add(QueuedFile(path: pf.path!, name: pf.name));
      }
    }
    notifyListeners();
    if (platformFiles.length == 1 && platformFiles.first.path != null) {
      analyzeFile(platformFiles.first.path!);
    }
  }

  void addFileFromDrop(String path, String name) {
    if (!_files.any((q) => q.path == path)) {
      _files.add(QueuedFile(path: path, name: name));
      if (_files.length == 1) analyzeFile(path);
      notifyListeners();
    }
  }

  void removeFile(int index) {
    _files.removeAt(index);
    // Clean up _fileStates for shifted indices
    _fileStates.remove(index);
    final shifted = <int, dynamic>{};
    for (final entry in _fileStates.entries) {
      if (entry.key > index) {
        shifted[entry.key - 1] = entry.value;
      } else {
        shifted[entry.key] = entry.value;
      }
    }
    _fileStates
      ..clear()
      ..addAll(shifted);
    if (_files.isEmpty) {
      _waveformData = null;
      _detectedBpm = null;
      _detectedKey = null;
    }
    notifyListeners();
  }

  void clearQueue() {
    _files.clear();
    _waveformData = null;
    _detectedBpm = null;
    _detectedKey = null;
    _downloadProgress = 0;
    _downloadStatus = '';
    _fileStates.clear();
    _audioSrcPath = null;
    stopPlayback();
    notifyListeners();
  }

  // ── File browsing ──────────────────────────────────────────────────────

  Future<void> browseFiles() async {
    final result = await FilePicker.platform.pickFiles(
      allowMultiple: true,
      type: FileType.custom,
      allowedExtensions: ['mp4', 'mkv', 'avi', 'mov', 'flv', 'mp3', 'wav', 'flac', 'ogg'],
    );
    if (result != null && result.files.isNotEmpty) {
      addFiles(result.files);
    }
  }

  // ── Audio analysis ─────────────────────────────────────────────────────

  List<double>? _waveformData;
  List<double>? get waveformData => _waveformData;
  double _durationSec = 0;
  double get durationSec => _durationSec;
  String? _detectedBpm;
  String? get detectedBpm => _detectedBpm;
  String? _detectedKey;
  String? get detectedKey => _detectedKey;

  Future<void> analyzeFile(String path) async {
    try {
      final resp = await api.analyzeAudio(path);
      if (resp['status'] == 'ok') {
        final analysis = resp['analysis'];
        _detectedBpm = analysis['bpm']?.toString();
        _detectedKey = analysis['key'];
        if (analysis['waveform'] != null) {
          _waveformData = List<double>.from(analysis['waveform']);
        }
        _durationSec = (analysis['full_duration_sec'] as num?)?.toDouble() ?? 0;
        // Set audio source path for playback
        _audioSrcPath = path;
        notifyListeners();
      }
    } catch (_) {}
  }

  // ── URL download ───────────────────────────────────────────────────────

  final _urlController = TextEditingController();
  TextEditingController get urlController => _urlController;

  bool _isDownloading = false;
  bool get isDownloading => _isDownloading;
  double _downloadProgress = 0;
  double get downloadProgress => _downloadProgress;
  String _downloadStatus = '';
  String get downloadStatus => _downloadStatus;
  String? _lastUrl;
  String? get lastUrl => _lastUrl;

  Future<void> downloadFromUrl() async {
    final url = _urlController.text.trim();
    if (url.isEmpty || !url.startsWith('http')) return;
    _lastUrl = url;
    _isDownloading = true;
    _downloadProgress = 0;
    _downloadStatus = 'Downloading...';
    _logLines.add('\u{1F310} $url');
    notifyListeners();

    try {
      final resp = await api.downloadUrl(url);
      if (resp['status'] == 'ok') {
        _isDownloading = false;
        _downloadProgress = 0;
        _downloadStatus = '';
        _files.add(QueuedFile(path: resp['file_path'], name: resp['filename']));
        _logLines.add('\u2705 ${resp["filename"]} (${resp["size_mb"]} MB)');
        notifyListeners();
        analyzeFile(resp['file_path']);
      }
    } catch (e) {
      _isDownloading = false;
      _downloadStatus = 'Error';
      _logLines.add('\u274C $e');
      notifyListeners();
    }
  }

  void cancelDownload() {
    _isDownloading = false;
    _downloadStatus = 'Cancelled';
    _logLines.add('\u2715 Cancelled');
    notifyListeners();
  }

  void retryDownload() {
    if (_lastUrl != null) {
      _logLines.add('\u21BB $_lastUrl');
      downloadFromUrl();
    }
  }

  // ── Output directory ───────────────────────────────────────────────────

  String? _outputDir;
  String? get outputDir => _outputDir;
  final _outputDirController = TextEditingController();
  TextEditingController get outputDirController => _outputDirController;

  Future<void> browseOutputDir() async {
    final result = await FilePicker.platform.getDirectoryPath(dialogTitle: 'Choose output folder');
    if (result != null) {
      _outputDir = result;
      _outputDirController.text = result;
      notifyListeners();
    }
  }

  // ── Real Audio Playback ───────────────────────────────────────────────

  final AudioPlayer _audioPlayer = AudioPlayer();
  String? _audioSrcPath;
  double _currentPosSec = 0;
  double get currentPosSec => _currentPosSec;
  bool _isPlaying = false;
  bool get isPlaying => _isPlaying;
  Timer? _playbackTimer;

  void togglePlayback() {
    _isPlaying ? pausePlayback() : startPlayback();
  }

  Future<void> startPlayback() async {
    if (_durationSec <= 0 || _audioSrcPath == null) return;

    if (_currentPosSec >= _durationSec) {
      _currentPosSec = 0;
    }

    // Use real audio file playback
    try {
      await _audioPlayer.stop();
      await _audioPlayer.play(DeviceFileSource(_audioSrcPath!));
      _isPlaying = true;
      // Seek to current position if not at start
      if (_currentPosSec > 0) {
        await _audioPlayer.seek(Duration(milliseconds: (_currentPosSec * 1000).toInt()));
      }
    } catch (_) {
      // Fallback: simulated timer if real playback fails
      _isPlaying = true;
    }

    notifyListeners();

    // Timer to track position for UI
    _playbackTimer?.cancel();
    _playbackTimer = Timer.periodic(const Duration(milliseconds: 200), (_) {
      if (_disposed) return;
      _audioPlayer.getCurrentPosition().then((pos) {
        if (_disposed) return;
        _currentPosSec = (pos?.inMilliseconds ?? (_currentPosSec * 1000).toInt()) / 1000.0;
        if (_currentPosSec >= _durationSec) {
          _currentPosSec = _durationSec;
          pausePlayback();
        }
        notifyListeners();
      }).catchError((_) {
        // Fallback increment if position query fails
        _currentPosSec += 0.2;
        if (_currentPosSec >= _durationSec) {
          _currentPosSec = _durationSec;
          pausePlayback();
        }
        notifyListeners();
      });
    });

    // Listen for player completion
    _audioPlayer.onPlayerComplete.listen((_) {
      if (!_disposed) {
        _currentPosSec = _durationSec;
        pausePlayback();
      }
    });
  }

  Future<void> pausePlayback() async {
    _playbackTimer?.cancel();
    _isPlaying = false;
    await _audioPlayer.pause();
    notifyListeners();
  }

  Future<void> stopPlayback() async {
    _playbackTimer?.cancel();
    _isPlaying = false;
    _currentPosSec = 0;
    await _audioPlayer.stop();
    notifyListeners();
  }

  Future<void> seekTo(double pos) async {
    _currentPosSec = pos.clamp(0, _durationSec);
    if (_isPlaying) {
      await _audioPlayer.seek(Duration(milliseconds: (_currentPosSec * 1000).toInt()));
    }
    notifyListeners();
  }

  // ── Separation ─────────────────────────────────────────────────────────

  bool _isProcessing = false;
  bool get isProcessing => _isProcessing;
  double _progress = 0;
  double get progress => _progress;
  String _statusText = '';
  String get statusText => _statusText;
  Color _statusColor = AppColors.success;
  Color get statusColor => _statusColor;
  final List<String> _logLines = [];
  List<String> get logLines => _logLines;

  // Default model — htdemucs offers the best CPU/GPU balance.
  // On this system, htdemucs is faster than mdx_q (3.8x vs 5.2x realtime).
  String _modelName = 'htdemucs';
  String get modelName => _modelName;
  set modelName(String v) { _modelName = v; notifyListeners(); }
  final Map<String, String> modelKeys = const {
    'htdemucs_ft': 'model_htdemucs_ft',
    'htdemucs': 'model_htdemucs',
    'htdemucs_6s': 'model_htdemucs_6s',
    'hdemucs_mmi': 'model_hdemucs_mmi',
    'mdx': 'model_mdx',
    'mdx_extra': 'model_mdx_extra',
    'mdx_q': 'model_mdx_q',
    'mdx_extra_q': 'model_mdx_extra_q',
  };

  String _outputFormat = 'wav';
  String get outputFormat => _outputFormat;
  set outputFormat(String v) { _outputFormat = v; notifyListeners(); }

  String _videoOutputMode = 'audio_only';
  String get videoOutputMode => _videoOutputMode;
  set videoOutputMode(String v) { _videoOutputMode = v; notifyListeners(); }

  bool _enableGate = true;
  bool get enableGate => _enableGate;
  set enableGate(bool v) { _enableGate = v; notifyListeners(); }

  bool _enableDenoise = true;
  bool get enableDenoise => _enableDenoise;
  set enableDenoise(bool v) { _enableDenoise = v; notifyListeners(); }

  bool _enableMultiband = false;
  bool get enableMultiband => _enableMultiband;
  set enableMultiband(bool v) { _enableMultiband = v; notifyListeners(); }

  bool _enableProfile = false;
  bool get enableProfile => _enableProfile;
  set enableProfile(bool v) { _enableProfile = v; notifyListeners(); }

  bool _adaptiveGate = false;
  bool get adaptiveGate => _adaptiveGate;
  set adaptiveGate(bool v) { _adaptiveGate = v; notifyListeners(); }

  bool _trimSilence = false;
  bool get trimSilence => _trimSilence;
  set trimSilence(bool v) { _trimSilence = v; notifyListeners(); }

  bool _karaokeMode = false;
  bool get karaokeMode => _karaokeMode;
  set karaokeMode(bool v) { _karaokeMode = v; notifyListeners(); }

  bool _ensembleMode = false;
  bool get ensembleMode => _ensembleMode;
  set ensembleMode(bool v) { _ensembleMode = v; notifyListeners(); }

  bool _includeSfx = true;
  bool get includeSfx => _includeSfx;
  set includeSfx(bool v) { _includeSfx = v; notifyListeners(); }

  bool _saveBg = false;
  bool get saveBg => _saveBg;
  set saveBg(bool v) { _saveBg = v; notifyListeners(); }

  // SFX is always enabled and mixed into the output — no standalone toggle needed.
  bool _enableSfxSep = false;
  bool get enableSfxSep => _enableSfxSep;
  set enableSfxSep(bool v) { _enableSfxSep = v; notifyListeners(); }

  bool _genSamples = false;
  bool get genSamples => _genSamples;
  set genSamples(bool v) { _genSamples = v; notifyListeners(); }

  bool _songMode = false;
  bool get songMode => _songMode;
  set songMode(bool v) { _songMode = v; notifyListeners(); }

  // ── Advanced settings (stored locally; also saved to API config via dialog) ─
  double _segment = 6.0;
  double get segment => _segment;
  set segment(double v) { _segment = v.clamp(2.0, 60.0); notifyListeners(); }

  double _overlap = 2.0;
  double get overlap => _overlap;
  set overlap(double v) { _overlap = v.clamp(0.1, 8.0); notifyListeners(); }

  int _shifts = 1;
  int get shifts => _shifts;
  set shifts(int v) { _shifts = v.clamp(1, 10); notifyListeners(); }

  double _gateThresholdDb = -55.0;
  double get gateThresholdDb => _gateThresholdDb;
  set gateThresholdDb(double v) { _gateThresholdDb = v.clamp(-80.0, -10.0); notifyListeners(); }

  double _gateFloorDb = -60.0;
  double get gateFloorDb => _gateFloorDb;
  set gateFloorDb(double v) { _gateFloorDb = v.clamp(-90.0, -20.0); notifyListeners(); }

  double _denoiseStrength = 0.55;
  double get denoiseStrength => _denoiseStrength;
  set denoiseStrength(double v) { _denoiseStrength = v.clamp(0.0, 1.0); notifyListeners(); }

  double _minVocalDuration = 0.08;
  double get minVocalDuration => _minVocalDuration;
  set minVocalDuration(double v) { _minVocalDuration = v.clamp(0.01, 1.0); notifyListeners(); }

  // ── Parallel workers ──────────────────────────────────────────────────

  int _parallelWorkers = 1;
  int get parallelWorkers => _parallelWorkers;
  set parallelWorkers(int v) { _parallelWorkers = v.clamp(1, 4); notifyListeners(); }

  // ── Per-file progress ─────────────────────────────────────────────────

  /// Per-file state: null = waiting, 0.0-1.0 = progress, 'done'/'error'/'cancelled' = terminal.
  final Map<int, dynamic> _fileStates = {};
  Map<int, dynamic> get fileStates => _fileStates;

  String? _lastOutputPath;
  String? get lastOutputPath => _lastOutputPath;
  String? _lastError;
  String? get lastError => _lastError;

  /// Auto-open the output folder in Explorer when separation completes.
  Future<void> openOutputFolder() async {
    final path = _lastOutputPath;
    if (path == null) return;
    // Extract parent directory from the output path
    final folder = path.contains(RegExp(r'[/\\]'))
        ? path.substring(0, path.lastIndexOf(RegExp(r'[/\\]')) + 1)
        : path;
    try {
      await OpenFilex.open(folder);
    } catch (_) {
      _logLines.add('\uD83D\uDCC2 Could not open: $folder');
      notifyListeners();
    }
  }

  // ── Workflow state ────────────────────────────────────────────────────

  /// Workflow phases displayed in the pipeline UI.
  static const workflowPhases = [
    _WorkflowPhase('idle', 'Queued'),
    _WorkflowPhase('initializing', 'Initializing'),
    _WorkflowPhase('separating', 'Separating'),
    _WorkflowPhase('postProcessing', 'Post-process'),
    _WorkflowPhase('exporting', 'Exporting'),
    _WorkflowPhase('done', 'Complete'),
  ];

  String _currentPhase = 'idle';
  String get currentPhase => _currentPhase;

  DateTime? _processingStartTime;
  DateTime? get processingStartTime => _processingStartTime;

  int _currentFileIndex = -1;
  int get currentFileIndex => _currentFileIndex;
  int _currentFileTotal = 0;
  int get currentFileTotal => _currentFileTotal;
  String? _currentFilename;
  String? get currentFilename => _currentFilename;

  double get elapsedSeconds => _processingStartTime != null
      ? DateTime.now().difference(_processingStartTime!).inMilliseconds / 1000.0
      : 0.0;

  /// Rolling-average ETA based on real progress updates.
  ///
  /// Collects (timestamp, progress) samples from real WebSocket/HTTP progress
  /// updates and computes the average processing rate (seconds per unit of
  /// progress) over the last few samples. This smooths out the jitter from
  /// estimated progress updates and creep, giving a stable ETA that gracefully
  /// converges to the true remaining time.
  ///
  /// Samples are stored in [_rateSamples] and reset on each new job.
  final List<_RateSample> _rateSamples = [];
  static const int _maxRateSamples = 5;

  double get estimatedTotalSeconds {
    final elapsed = elapsedSeconds;
    if (elapsed < 5) return 0.0; // Too early — no meaningful estimate yet

    // If we have enough real samples, use rolling average
    if (_rateSamples.length >= 2) {
      final first = _rateSamples.first;
      final last = _rateSamples.last;
      final dt = last.timestamp.difference(first.timestamp).inMilliseconds / 1000.0;
      final dp = last.progress - first.progress;
      if (dp > 0.01 && dt > 2) {
        final rate = dt / dp; // seconds per unit of progress
        final remaining = 1.0 - last.progress;
        return elapsed + rate * remaining;
      }
    }

    // Fallback: use the instantaneous rate but only if progress is meaningful
    if (_progress > 0.05) {
      return elapsed / _progress;
    }
    return 0.0;
  }

  double get etaSeconds {
    final est = estimatedTotalSeconds;
    return est > 0 ? (est - elapsedSeconds).clamp(0, double.infinity) : 0.0;
  }

  void _addRateSample(double progress) {
    // Only record real updates (≥2% change from last sample) to avoid
    // adding noise from creep or tiny estimated updates.
    if (_rateSamples.isNotEmpty) {
      final last = _rateSamples.last.progress;
      if ((progress - last).abs() < 0.02) return;
      // Ignore regressions (shouldn't happen, but handle it)
      if (progress < last) return;
    }
    _rateSamples.add(_RateSample(DateTime.now(), progress));
    if (_rateSamples.length > _maxRateSamples) {
      _rateSamples.removeAt(0);
    }
  }

  // Internal tick timer to refresh elapsed/ETA display
  Timer? _workflowTimer;
  // HTTP polling timer (fallback when WebSocket events are lost)
  Timer? _pollTimer;
  // Job ID for HTTP polling
  String? _pollingJobId;
  // Prevents overlapping poll requests
  bool _isPollingInFlight = false;

  void _startWorkflowTimer() {
    _workflowTimer?.cancel();
    _pollTimer?.cancel(); // Stale poll timer from a previous job
    _isPollingInFlight = false;
    _lastProgressTime = DateTime.now();
    _lastRealProgress = 0.0;
    _displayedProgress = 0.0;

    _workflowTimer = Timer.periodic(const Duration(milliseconds: 500), (_) {
      if (_disposed) {
        _workflowTimer?.cancel();
        return;
      }

      // Smooth progress animation: between real updates, slowly creep up
      // the displayed progress so the bar doesn't appear frozen.
      // Uses a linear 2%/s creep: each 500ms tick adds 1% (0.01),
      // so the bar visibly climbs even during long model loading phases.
      // Never drops the bar (builds on current _displayedProgress),
      // and never exceeds 50% of the gap to the next real update.
      if (_isProcessing) {
        final elapsed = DateTime.now().difference(_lastProgressTime).inMilliseconds / 1000.0;
        if (elapsed > 2 && _lastRealProgress < 0.95) {
          // After 2s without update, add 1% per tick (linear 2%/s).
          // Builds on _displayedProgress so the bar can never drop.
          final maxDisplay = _lastRealProgress + (1.0 - _lastRealProgress) * 0.5;
          _displayedProgress = (_displayedProgress + 0.01).clamp(0.0, maxDisplay);
          _progress = _displayedProgress;
        }
      }

      _throttledNotify(); // refresh elapsed/ETA display and progress
    });
  }

  void _stopWorkflowTimer() {
    _workflowTimer?.cancel();
    _workflowTimer = null;
    _pollTimer?.cancel();
    _pollTimer = null;
    _pollingJobId = null;
  }

  /// Start HTTP polling for a job as a fallback when WebSocket events
  /// are lost or delayed. Polls every 2s and updates the controller state
  /// directly from the API response.
  void startPollingJob(String jobId) {
    _pollingJobId = jobId;
    _pollTimer?.cancel();
    _isPollingInFlight = false;
    _pollTimer = Timer.periodic(const Duration(seconds: 2), (_) async {
      if (_disposed || !_isProcessing || _pollingJobId == null || _isPollingInFlight) {
        if (!_isProcessing) {
          _pollTimer?.cancel();
          _pollTimer = null;
        }
        return;
      }
      _isPollingInFlight = true;
      try {
        final resp = await api.getJob(_pollingJobId!);
        final job = resp['job'] as Map<String, dynamic>?;
        if (job == null) return;
        final status = job['status'] as String?;

        switch (status) {
          case 'completed':
            _isProcessing = false;
            _lastRealProgress = 1.0;
            _displayedProgress = 1.0;
            _progress = 1.0;
            _currentPhase = 'done';
            _statusText = 'Complete';
            _statusColor = AppColors.success;
            _lastOutputPath = job['output_path'] as String?;
            _stopWorkflowTimer();
            onSeparationComplete?.call(_lastOutputPath);
            break;
          case 'error':
            _isProcessing = false;
            _currentPhase = 'error';
            _statusText = 'Error';
            _statusColor = AppColors.error;
            _lastError = job['error'] as String?;
            _stopWorkflowTimer();
            break;
          case 'cancelled':
            _isProcessing = false;
            _currentPhase = 'cancelled';
            _statusText = 'Cancelled';
            _statusColor = AppColors.warning;
            _stopWorkflowTimer();
            break;
          default:
            // Update progress from total_progress if available
            final tp = (job['total_progress'] as num?)?.toDouble() ?? -1.0;
            if (tp >= 0) {
              _lastRealProgress = tp;
              // Only update displayed progress AND reset creep timer when
              // progress actually increased — prevents HTTP polling every 2s
              // from resetting the creep timer with the same (stale) value.
              if (tp > _displayedProgress) {
                _displayedProgress = tp;
                _lastProgressTime = DateTime.now();
                _addRateSample(tp);
              }
              _progress = _displayedProgress;
              final st = job['status_text'] as String? ?? '';
              if (st.isNotEmpty) _detectPhase(st);
            }
        }
        notifyListeners();
      } catch (_) {
      } finally {
        _isPollingInFlight = false;
      }
    });
  }

  void _detectPhase(String message) {
    final lower = message.toLowerCase();
    if (lower.contains('initializ') || lower.contains('loading model') || lower.contains('preparing')) {
      _currentPhase = 'initializing';
    } else if (lower.contains('separat') || lower.contains('demucs') || lower.contains('inference')) {
      _currentPhase = 'separating';
    } else if (lower.contains('post-process') || lower.contains('denois') || lower.contains('gate') ||
               lower.contains('vad') || lower.contains('trim') || lower.contains('silence')) {
      _currentPhase = 'postProcessing';
    } else if (lower.contains('export') || lower.contains('saving') || lower.contains('writ') ||
               lower.contains('conver') || lower.contains('mux') || lower.contains('video') ||
               lower.contains('sample') || lower.contains('comparison')) {
      _currentPhase = 'exporting';
    }
  }

  static String formatDuration(double seconds) {
    if (seconds <= 0) return '--';
    final m = (seconds ~/ 60).toInt();
    final s = (seconds % 60).toInt();
    if (m >= 60) {
      final h = m ~/ 60;
      return '${h}h ${m % 60}m';
    }
    return m > 0 ? '${m}m ${s}s' : '${s}s';
  }

  // ── Progress events (called from WebSocket stream) ─────────────────────

  /// Last real progress value received from the backend (for smooth animation).
  double _lastRealProgress = 0.0;
  /// Time when the last real progress update was received.
  DateTime _lastProgressTime = DateTime.now();
  /// Displayed progress (may differ from real when animating).
  double _displayedProgress = 0.0;

  void _onProgressEvent(ProgressEvent event) {
    if (_disposed) return;
    final fi = event.index; // may be null for legacy events

    switch (event.type) {
      case ProgressType.progress:
        _lastRealProgress = (event.percent ?? 0) / 100;
        // Record this real update for the rolling-average ETA
        _addRateSample(_lastRealProgress);
        // Don't drop displayed progress below where creep has pushed it,
        // to avoid a jarring backward jump when a real update arrives.
        if (_lastRealProgress > _displayedProgress) {
          _displayedProgress = _lastRealProgress;
        }
        _lastProgressTime = DateTime.now();
        _progress = _displayedProgress;
        _statusText = event.message ?? 'Processing...';
        _detectPhase(event.message ?? '');
        // Track per-file progress if indexed
        if (fi != null) {
          _fileStates[fi] = (event.percent ?? 0) / 100;
        }
        _logLines.add(event.message ?? '');
        break;
      case ProgressType.fileStart:
        _currentFileIndex = event.index ?? 0;
        _currentFileTotal = event.total ?? 1;
        _currentFilename = event.filename;
        _fileStates[_currentFileIndex] = 0.0; // started
        _logLines.add('[${event.index! + 1}/${event.total}] ${event.filename}');
        break;
      case ProgressType.done:
        _isProcessing = false;
        _lastRealProgress = 1.0;
        _displayedProgress = 1.0;
        _progress = 1.0;
        _currentPhase = 'done';
        _statusText = 'Complete';
        _statusColor = AppColors.success;
        _lastOutputPath = event.outputPath;
        // Mark all files as done
        for (final k in _fileStates.keys.toList()) {
          _fileStates[k] = 'done';
        }
        _logLines.add('\u2705 Complete');
        _stopWorkflowTimer();
        // Fire completion callback
        onSeparationComplete?.call(event.outputPath);
        break;
      case ProgressType.error:
        _isProcessing = false;
        _currentPhase = 'error';
        _statusText = 'Error';
        _statusColor = AppColors.error;
        _lastError = event.message;
        _logLines.add('\u274C ${event.message}');
        if (fi != null) _fileStates[fi] = 'error';
        _progress = _displayedProgress; // stay where the user last saw it
        _stopWorkflowTimer();
        break;
      case ProgressType.cancelled:
        _isProcessing = false;
        _currentPhase = 'cancelled';
        _statusText = 'Cancelled';
        _statusColor = AppColors.warning;
        _logLines.add('\u2715 Cancelled');
        for (final k in _fileStates.keys.toList()) {
          if (_fileStates[k] == null || _fileStates[k] is double) {
            _fileStates[k] = 'cancelled';
          }
        }
        _stopWorkflowTimer();
        break;
      case ProgressType.pong:
        break;
      case ProgressType.reconnected:
        // Server restarted — if we were processing, the job was lost.
        if (_isProcessing) {
          _isProcessing = false;
          _currentPhase = 'error';
          _statusText = 'Server disconnected — check if the backend is running';
          _statusColor = AppColors.error;
          _lastError = 'The AI server was restarted. Your previous job was lost. Please try again.';
          _logLines.add('\u26A0\uFE0F Server reconnected — previous job lost');
          _stopWorkflowTimer();
        }
        break;
    }
    // Throttle: progress events flood in at ~10/sec, but done/error/cancelled
    // must always notify immediately. Terminal events and phase changes get
    // instant notification; progress updates are throttled to 100ms.
    final isTerminal = event.type == ProgressType.done ||
        event.type == ProgressType.error ||
        event.type == ProgressType.cancelled ||
        event.type == ProgressType.reconnected;
    if (isTerminal) {
      notifyListeners();
    } else {
      _throttledNotify();
    }
  }

  /// Override status text with a localized string.
  void setStatusText(String text, {Color color = AppColors.success}) {
    _statusText = text;
    _statusColor = color;
    notifyListeners();
  }

  // ── Actions ────────────────────────────────────────────────────────────

  /// Prepare controller for a job launched via JobManager.
  /// Sets processing state and starts the workflow timer.
  void prepareForJob() {
    if (_files.isEmpty || _isProcessing) return;
    _isProcessing = true;
    _progress = 0;
    _resetRateSamples();
    _currentPhase = 'initializing';
    _currentFileIndex = -1;
    _currentFileTotal = _files.length;
    _currentFilename = null;
    _lastError = null;
    _processingStartTime = DateTime.now();
    _fileStates.clear();
    for (int i = 0; i < _files.length; i++) {
      _fileStates[i] = null;
    }
    _statusText = 'Starting job...';
    _statusColor = AppColors.warning;
    _logLines.clear();
    _startWorkflowTimer();
    notifyListeners();
  }

  void _resetRateSamples() {
    _rateSamples.clear();
  }

  /// Report a job error (API failure, server not running, etc.).
  void onJobError(String errorMessage) {
    if (_disposed) return;
    _isProcessing = false;
    _currentPhase = 'error';
    _statusText = errorMessage;
    _statusColor = AppColors.error;
    _lastError = errorMessage;
    _logLines.add('\u274C $errorMessage');
    _stopWorkflowTimer();
    notifyListeners();
  }

  /// Legacy direct-separation method (no longer wired in UI).
  Future<void> startSeparation() async {
    if (_files.isEmpty || _isProcessing) return;
    prepareForJob();
    try {
      await api.startSeparation(
        filePaths: _files.map((f) => f.path).toList(),
        outputDir: _outputDir,
        modelName: _modelName,
        outputFormat: _outputFormat,
        parallelWorkers: _parallelWorkers,
        enableGate: _enableGate,
        enableDenoise: _enableDenoise,
        enableMultiband: _enableMultiband,
        enableProfile: _enableProfile,
        adaptiveGate: _adaptiveGate,
        karaokeMode: _songMode ? false : _karaokeMode,
        ensembleMode: _ensembleMode,
        includeSfx: _songMode ? false : _includeSfx,
        saveBg: _songMode ? false : _saveBg,
        genSamples: _genSamples,
        enableSfxSep: _enableSfxSep,
        videoOutputMode: _songMode ? 'audio_only' : _videoOutputMode,
        trimSilence: _songMode ? true : _trimSilence,
      );
    } catch (e) {
      if (_disposed) return;
      onJobError('$e');
    }
  }

  Future<void> cancel() async {
    await api.cancelSeparation();
    if (_isProcessing) {
      _isProcessing = false;
      _currentPhase = 'cancelled';
      _statusText = 'Cancelled';
      _statusColor = AppColors.warning;
      _stopWorkflowTimer();
      notifyListeners();
    }
  }

  void setLogLines(List<String> lines) {
    _logLines.clear();
    _logLines.addAll(lines);
    notifyListeners();
  }

  void addLogLine(String line) {
    _logLines.add(line);
    notifyListeners();
  }

  void clearLog() {
    _logLines.clear();
    notifyListeners();
  }

  // ── Advanced dialog ────────────────────────────────────────────────────

  void showAdvancedDialog(BuildContext context) {
    final l10n = AppLocalizations.instance(context);
    // Conservative defaults that work on CPU; backend auto-detects
    // hardware and further optimizes if needed.
    Map<String, double> tempVals = {
      'segment': 6.0,
      'overlap': 2.0,
      'shifts': 1,
      'gate_threshold_db': -55.0,
      'gate_floor_db': -60.0,
      'denoise_strength': 0.55,
    };

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          backgroundColor: AppColors.surface,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: Text(l10n.fineTune, style: AppTextStyles.subheading(context)),
          content: SizedBox(
            width: 400,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  _dialogSlider(context, 'Segment (sec)', tempVals, 'segment', 2.0, 60.0, false, setDialogState),
                  _dialogSlider(context, 'Overlap (sec)', tempVals, 'overlap', 0.1, 8.0, false, setDialogState),
                  _dialogSlider(context, 'Shifts', tempVals, 'shifts', 1, 10, true, setDialogState),
                  const SizedBox(height: 4),
                  const Divider(color: AppColors.glassBorder, height: 16),
                  Text('Gate & Noise', style: AppTextStyles.label(context)),
                  const SizedBox(height: 4),
                  _dialogSlider(context, 'Gate Threshold (dB)', tempVals, 'gate_threshold_db', -80.0, -10.0, false, setDialogState),
                  _dialogSlider(context, 'Gate Floor (dB)', tempVals, 'gate_floor_db', -90.0, -20.0, false, setDialogState),
                  _dialogSlider(context, 'Denoise Strength', tempVals, 'denoise_strength', 0.0, 1.0, false, setDialogState),
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppColors.surfaceLight,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      'More settings available in Settings \u2192 Advanced Tuning',
                      style: AppTextStyles.caption(context),
                    ),
                  ),
                ],
              ),
            ),
          ),
          actions: [
            GhostButton(label: l10n.cancel, onPressed: () => Navigator.pop(ctx)),
            const SizedBox(width: 8),
            AccentButton(label: l10n.get('save'), onPressed: () {
              for (final entry in tempVals.entries) {
                api.updateConfig(entry.key, entry.value);
              }
              addLogLine('\u2699\uFE0F Advanced settings saved');
              Navigator.pop(ctx);
            }),
          ],
        ),
      ),
    );
  }

  Widget _dialogSlider(
    BuildContext context, String label, Map<String, double> vals, String key,
    double min, double max, bool isInt, StateSetter setDialogState,
  ) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          Text(label, style: AppTextStyles.body(context).copyWith(fontSize: 12)),
          Text(isInt ? vals[key]!.toInt().toString() : vals[key]!.toStringAsFixed(1),
            style: AppTextStyles.body(context).copyWith(color: AppColors.accentPurple, fontWeight: FontWeight.w600)),
        ]),
        SliderTheme(data: SliderThemeData(
          activeTrackColor: AppColors.accentPurple,
          thumbColor: AppColors.accentPurple,
          overlayColor: AppColors.accentPurple.withValues(alpha: 0.15),
          inactiveTrackColor: AppColors.surfaceLight,
          trackHeight: 3,
          thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 6),
        ), child: Slider(
          value: vals[key]!.clamp(min, max),
          min: min, max: max,
          divisions: isInt ? (max - min).toInt() : null,
          onChanged: (v) => setDialogState(() => vals[key] = isInt ? v.roundToDouble() : v),
        )),
      ]),
    );
  }

  // ── Keyboard events ────────────────────────────────────────────────────

  void handleKeyEvent(KeyEvent event) {
    final ctrl = HardwareKeyboard.instance.isControlPressed;
    if (event is KeyDownEvent) {
      if (event.logicalKey == LogicalKeyboardKey.keyO && ctrl) {
        browseFiles();
      } else if (event.logicalKey == LogicalKeyboardKey.keyR && ctrl) {
        onStartNewJob?.call();
      } else if (event.logicalKey == LogicalKeyboardKey.escape) {
        if (_isProcessing) cancel();
      }
    }
  }
}

/// A named phase in the workflow pipeline.
class _WorkflowPhase {
  final String id;
  final String label;
  const _WorkflowPhase(this.id, this.label);
}

/// A (timestamp, progress) pair used for rolling-average ETA calculation.
class _RateSample {
  final DateTime timestamp;
  final double progress;
  const _RateSample(this.timestamp, this.progress);
}

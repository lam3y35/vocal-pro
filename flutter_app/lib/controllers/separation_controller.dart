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

  SeparationController({required this.api, AppLocalizations? l10n})
      : _statusText = l10n?.readyLog ?? 'Ready' {
    _wsSub = api.onProgress.listen(_onProgressEvent);
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

  // Settings
  String _modelName = 'htdemucs_ft';
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

  String _videoOutputMode = 'both';
  String get videoOutputMode => _videoOutputMode;
  set videoOutputMode(String v) { _videoOutputMode = v; notifyListeners(); }

  bool _enableGate = true;
  bool get enableGate => _enableGate;
  set enableGate(bool v) { _enableGate = v; notifyListeners(); }

  bool _enableDenoise = true;
  bool get enableDenoise => _enableDenoise;
  set enableDenoise(bool v) { _enableDenoise = v; notifyListeners(); }

  bool _enableMultiband = true;
  bool get enableMultiband => _enableMultiband;
  set enableMultiband(bool v) { _enableMultiband = v; notifyListeners(); }

  bool _enableProfile = true;
  bool get enableProfile => _enableProfile;
  set enableProfile(bool v) { _enableProfile = v; notifyListeners(); }

  bool _adaptiveGate = true;
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

  bool _enableSfxSep = true;
  bool get enableSfxSep => _enableSfxSep;
  set enableSfxSep(bool v) { _enableSfxSep = v; notifyListeners(); }

  bool _genSamples = true;
  bool get genSamples => _genSamples;
  set genSamples(bool v) { _genSamples = v; notifyListeners(); }

  bool _songMode = false;
  bool get songMode => _songMode;
  set songMode(bool v) { _songMode = v; notifyListeners(); }

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

  double get estimatedTotalSeconds => _progress > 0.01
      ? elapsedSeconds / _progress
      : 0.0;

  double get etaSeconds {
    final est = estimatedTotalSeconds;
    return est > 0 ? (est - elapsedSeconds).clamp(0, double.infinity) : 0.0;
  }

  // Internal tick timer to refresh elapsed/ETA display
  Timer? _workflowTimer;

  void _startWorkflowTimer() {
    _workflowTimer?.cancel();
    _workflowTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (_disposed) {
        _workflowTimer?.cancel();
        return;
      }
      notifyListeners(); // refresh elapsed/ETA display
    });
  }

  void _stopWorkflowTimer() {
    _workflowTimer?.cancel();
    _workflowTimer = null;
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

  void _onProgressEvent(ProgressEvent event) {
    if (_disposed) return;
    final fi = event.index; // may be null for legacy events

    switch (event.type) {
      case ProgressType.progress:
        _progress = (event.percent ?? 0) / 100;
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
    }
    notifyListeners();
  }

  /// Override status text with a localized string.
  void setStatusText(String text, {Color color = AppColors.success}) {
    _statusText = text;
    _statusColor = color;
    notifyListeners();
  }

  // ── Actions ────────────────────────────────────────────────────────────

  Future<void> startSeparation() async {
    if (_files.isEmpty || _isProcessing) return;
    _isProcessing = true;
    _progress = 0;
    _currentPhase = 'initializing';
    _currentFileIndex = -1;
    _currentFileTotal = _files.length;
    _currentFilename = null;
    _processingStartTime = DateTime.now();
    _fileStates.clear();
    // Initialise all files as waiting
    for (int i = 0; i < _files.length; i++) {
      _fileStates[i] = null; // waiting
    }
    _statusText = 'Initializing...';
    _statusColor = AppColors.warning;
    _logLines.clear();
    _startWorkflowTimer();
    notifyListeners();

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
      _isProcessing = false;
      _currentPhase = 'error';
      _statusText = 'Error';
      _statusColor = AppColors.error;
      _logLines.add('\u274C $e');
      _stopWorkflowTimer();
      notifyListeners();
    }
  }

  Future<void> cancel() async {
    await api.cancelSeparation();
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
    Map<String, double> tempVals = {
      'segment': 24.0,
      'overlap': 2.0,
      'shifts': 5.0,
      'gate_threshold_db': -55.0,
      'gate_floor_db': -60.0,
      'denoise_strength': 0.65,
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
        startSeparation();
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

import 'dart:async';

import 'package:flutter/material.dart';
import '../models/separation_job.dart';
import '../services/api_service.dart';

/// Manages multiple concurrent separation jobs.
/// Each job has its own state, and the UI shows tabs for each job.
class JobManagerController extends ChangeNotifier {
  final ApiService _api;

  JobManagerController({required this._api}) {
    // Using initializing formal via assignment for clarity with the underscore field
    _wsSub = _api.onProgress.listen(_onProgressEvent);
  }

  // ── Jobs ──────────────────────────────────────────────────────────────

  final List<SeparationJob> _jobs = [];
  List<SeparationJob> get jobs => List.unmodifiable(_jobs);

  // Active job IDs (not yet auto-cleared)
  final Set<String> _activeJobIds = {};

  // Completed jobs recently auto-cleared (to prevent re-adding)
  final Set<String> _clearedJobIds = {};

  // ── Lifecycle ─────────────────────────────────────────────────────────

  bool _disposed = false;
  StreamSubscription<ProgressEvent>? _wsSub;
  Timer? _pollTimer;

  @override
  void dispose() {
    _disposed = true;
    _wsSub?.cancel();
    _pollTimer?.cancel();
    super.dispose();
  }

  // ── Job lifecycle ─────────────────────────────────────────────────────

  /// Start a new separation job and return the job_id.
  /// Throws on API/network errors — caller should catch and display the message.
  Future<String?> startJob(Map<String, dynamic> params) async {
    final resp = await _api.startSeparation(
      filePaths: List<String>.from(params['file_paths'] ?? []),
      outputDir: params['output_dir'] as String?,
      modelName: params['model_name'] as String? ?? 'htdemucs',
      outputFormat: params['output_format'] as String? ?? 'wav',
      enableGate: params['enable_gate'] as bool? ?? true,
      enableDenoise: params['enable_denoise'] as bool? ?? true,
      enableMultiband: params['enable_multiband'] as bool? ?? false,
      enableProfile: params['enable_profile'] as bool? ?? false,
      adaptiveGate: params['adaptive_gate'] as bool? ?? false,
      trimSilence: params['trim_silence'] as bool? ?? false,
      karaokeMode: params['karaoke_mode'] as bool? ?? false,
      ensembleMode: params['ensemble_mode'] as bool? ?? false,
      includeSfx: params['include_sfx'] as bool? ?? true,
      saveBg: params['save_bg'] as bool? ?? false,
      genSamples: params['gen_samples'] as bool? ?? false,
      enableSfxSep: params['enable_sfx_sep'] as bool? ?? false,
      segment: params['segment'] as double? ?? 6.0,
      overlap: params['overlap'] as double? ?? 2.0,
      shifts: params['shifts'] as int? ?? 1,
      gateThresholdDb: params['gate_threshold_db'] as double? ?? -55.0,
      gateFloorDb: params['gate_floor_db'] as double? ?? -60.0,
      denoiseStrength: params['denoise_strength'] as double? ?? 0.55,
      minVocalDuration: params['min_vocal_duration'] as double? ?? 0.08,
      videoOutputMode: params['video_output_mode'] as String? ?? 'both',
      parallelWorkers: params['parallel_workers'] as int? ?? 1,
    );
    final jobId = resp['job_id'] as String?;
    if (jobId != null) {
      _activeJobIds.add(jobId);
      final files = List<String>.from(params['file_paths'] ?? []);
      _jobs.add(SeparationJob(
        jobId: jobId,
        status: 'queued',
        files: files,
        totalFiles: files.length,
      ));
      notifyListeners();
      _startPolling();
    }
    return jobId;
  }

  /// Cancel a specific job.
  Future<void> cancelJob(String jobId) async {
    try {
      await _api.cancelJob(jobId);
      _updateJobInList(jobId, status: 'cancelled');
      notifyListeners();
    } catch (e) {
      debugPrint('Cancel job error: $e');
    }
  }

  /// Dismiss a completed job (remove from active list).
  void dismissJob(String jobId) {
    _jobs.removeWhere((j) => j.jobId == jobId);
    _activeJobIds.remove(jobId);
    _clearedJobIds.add(jobId);
    notifyListeners();
  }

  /// Get a specific job by ID.
  SeparationJob? getJob(String jobId) {
    try {
      return _jobs.firstWhere((j) => j.jobId == jobId);
    } catch (_) {
      return null;
    }
  }

  // ── Polling ───────────────────────────────────────────────────────────

  bool _isPolling = false;

  void _startPolling() {
    if (_isPolling) return;
    _isPolling = true;
    _pollJobs();
    _pollTimer = Timer.periodic(const Duration(seconds: 3), (_) {
      if (!_disposed) _pollJobs();
    });
  }

  void _stopPollingIfIdle() {
    final hasRunning = _jobs.any((j) => j.isRunning);
    if (!hasRunning) {
      _isPolling = false;
      _pollTimer?.cancel();
      _pollTimer = null;
    }
  }

  Future<void> _pollJobs() async {
    try {
      final jobsData = await _api.listJobs();
      bool changed = false;

      for (final jd in jobsData) {
        final jid = jd['job_id'] as String?;
        if (jid == null || _clearedJobIds.contains(jid)) continue;

        final existing = getJob(jid);
        if (existing != null) {
          // Update existing job
          final updated = SeparationJob.fromJson(jd);
          _updateJobInList(jid, job: updated);
          changed = true;
        } else if (_activeJobIds.contains(jid)) {
          // Job appeared but we haven't seen it yet
          final newJob = SeparationJob.fromJson(jd);
          // Avoid duplicates
          if (getJob(jid) == null) {
            _jobs.add(newJob);
            changed = true;
          }
        }
      }

      // Auto-clear completed jobs after a few seconds
      final now = DateTime.now();
      final toClear = <String>[];
      for (final job in _jobs) {
        if (job.isTerminal && job.completedAt != null) {
          if (now.difference(job.completedAt!).inSeconds > 15) {
            toClear.add(job.jobId);
          }
        }
      }
      for (final jid in toClear) {
        _jobs.removeWhere((j) => j.jobId == jid);
        _activeJobIds.remove(jid);
        _clearedJobIds.add(jid);
        changed = true;
      }

      if (changed) notifyListeners();
    } catch (_) {}

    _stopPollingIfIdle();
  }

  // ── WebSocket event handling ──────────────────────────────────────────

  void _onProgressEvent(ProgressEvent event) {
    if (_disposed) return;

    // Find the matching job (WebSocket events now include job_id)
    // If the event doesn't have a job_id, fall back to the first running job
    String? jobId = event.jobId;

    if (jobId == null) {
      // Legacy event without job_id — try first running job
      for (final job in _jobs) {
        if (job.isRunning) {
          jobId = job.jobId;
          break;
        }
      }
    }

    if (jobId == null) return;

    final existing = getJob(jobId);
    if (existing == null) {
      // Unknown job — might be from before restart; ignore
      return;
    }

    final fi = event.index;
    final progress = Map<int, dynamic>.from(existing.progress);

    switch (event.type) {
      case ProgressType.progress:
        final pct = (event.percent ?? 0) / 100;
        _updateJobInList(jobId, totalProgress: pct, statusText: event.message ?? '');
        if (fi != null) progress[fi] = pct;
        break;
      case ProgressType.fileStart:
        _updateJobInList(jobId,
          currentFile: event.index ?? 0,
          currentFilename: event.filename,
          statusText: 'Processing ${event.filename}...',
        );
        if (fi != null) progress[fi] = 0.0;
        break;
      case ProgressType.done:
        _updateJobInList(jobId,
          status: 'completed',
          totalProgress: 1.0,
          statusText: 'Complete',
          completedAt: DateTime.now(),
          outputPath: event.outputPath,
        );
        break;
      case ProgressType.error:
        _updateJobInList(jobId,
          status: 'error',
          error: event.message,
          statusText: 'Error',
          completedAt: DateTime.now(),
        );
        if (fi != null) progress[fi] = 'error';
        break;
      case ProgressType.cancelled:
        _updateJobInList(jobId,
          status: 'cancelled',
          statusText: 'Cancelled',
          completedAt: DateTime.now(),
        );
        break;
      case ProgressType.pong:
        break;
      case ProgressType.reconnected:
        // Server restarted — mark all active jobs as lost.
        for (final job in _jobs) {
          if (job.isRunning) {
            _updateJobInList(job.jobId,
              status: 'error',
              error: 'Server disconnected — job lost',
              statusText: 'Server Restart',
              completedAt: DateTime.now(),
            );
          }
        }
        // Re-poll to refresh job list from new server
        _pollJobs();
        break;
    }

    _updateJobInList(jobId, progress: progress);
    notifyListeners();
  }

  // ── Helper ────────────────────────────────────────────────────────────

  void _updateJobInList(String jobId, {SeparationJob? job, String? status, double? totalProgress, String? statusText, String? error, String? outputPath, Map<int, dynamic>? progress, int? currentFile, int? totalFiles, String? currentFilename, DateTime? completedAt}) {
    final idx = _jobs.indexWhere((j) => j.jobId == jobId);
    if (idx == -1) return;

    if (job != null) {
      _jobs[idx] = job;
      return;
    }

    final existing = _jobs[idx];
    _jobs[idx] = SeparationJob(
      jobId: existing.jobId,
      status: status ?? existing.status,
      files: existing.files,
      progress: progress ?? existing.progress,
      outputPaths: existing.outputPaths,
      totalProgress: totalProgress ?? existing.totalProgress,
      statusText: statusText ?? existing.statusText,
      currentFile: currentFile ?? existing.currentFile,
      totalFiles: totalFiles ?? existing.totalFiles,
      currentFilename: currentFilename ?? existing.currentFilename,
      error: error ?? existing.error,
      createdAt: existing.createdAt,
      completedAt: completedAt ?? existing.completedAt,
      outputPath: outputPath ?? existing.outputPath,
    );
  }
}

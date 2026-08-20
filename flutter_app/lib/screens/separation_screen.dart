import 'package:flutter/material.dart';
import '../controllers/separation_controller.dart';
import '../controllers/job_manager.dart';
import '../theme.dart';
import '../services/api_service.dart';
import '../services/backend_service.dart';
import '../l10n/app_localizations.dart';
import '../l10n/locale_provider.dart';
import '../widgets/separation/file_card.dart';
import '../widgets/separation/model_card.dart';
import '../widgets/separation/song_mode_card.dart';
import '../widgets/separation/options_card.dart';
import '../widgets/separation/download_card.dart';
import '../widgets/separation/log_card.dart';
import '../widgets/separation/job_tab.dart';
import '../widgets/cards.dart';

/// Separation screen – tabbed interface with "New Job" tab + per-job tabs.
class SeparationScreen extends StatefulWidget {
  final ApiService api;
  final LocaleProvider localeProvider;
  /// Optional pre-built controller (used by tests to inject a controlled instance).
  final SeparationController? controller;
  /// Backend service for server retry when the AI server is offline.
  final BackendService? backendService;
  const SeparationScreen({
    super.key,
    required this.api,
    required this.localeProvider,
    this.controller,
    this.backendService,
  });

  @override
  State<SeparationScreen> createState() => _SeparationScreenState();
}

class _SeparationScreenState extends State<SeparationScreen>
    with SingleTickerProviderStateMixin {
  late final SeparationController _ctrl;
  late final JobManagerController _jobManager;
  late TabController _tabController;
  final FocusNode _focusNode = FocusNode();

  @override
  void initState() {
    super.initState();
    // Create controller WITHOUT localization (avoids InheritedWidget access before
    // the widget is in the tree — critical for test compatibility).
    // If a controller was injected (e.g. by tests), use it directly.
    _ctrl = widget.controller ?? SeparationController(
      api: widget.api,
    );
    _jobManager = JobManagerController(api: widget.api);
    _tabController = TabController(length: 1, vsync: this);    // Start with just the "New Job" tab

    // ── CRITICAL: Listen to controllers so the UI rebuilds on state changes ──
    _ctrl.addListener(_onCtrlChanged);
    _jobManager.addListener(_onJobManagerChanged);

    // Wire Ctrl+R keyboard shortcut to use the job system
    _ctrl.onStartNewJob = () => _startNewJob(_ctrl, _jobManager);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Set localized status text now that InheritedWidgets are available.
    // This is safe because the widget is guaranteed to be in the tree.
    if (_ctrl.statusText.isEmpty || _ctrl.statusText == 'Ready') {
      final l10n = AppLocalizations.instance(context);
      _ctrl.setStatusText(l10n.readyLog, color: AppColors.success);
    }
  }

  @override
  void dispose() {
    _ctrl.removeListener(_onCtrlChanged);
    _ctrl.dispose();
    _jobManager.removeListener(_onJobManagerChanged);
    _jobManager.dispose();
    _tabController.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _onCtrlChanged() {
    if (mounted) setState(() {});
  }

  void _onJobManagerChanged() {
    if (!mounted) return;
    // Rebuild tabs when job count changes
    _rebuildTabsIfNeeded();
    setState(() {});
  }

  /// Start a new separation job with the current controller settings.
  Future<void> _startNewJob(SeparationController ctrl, JobManagerController jobManager) async {
    final params = <String, dynamic>{
      'file_paths': ctrl.files.map((f) => f.path).toList(),
      'output_dir': ctrl.outputDir,
      'model_name': ctrl.modelName,
      'output_format': ctrl.outputFormat,
      'enable_gate': ctrl.enableGate,
      'enable_denoise': ctrl.enableDenoise,
      'enable_multiband': ctrl.enableMultiband,
      'enable_profile': ctrl.enableProfile,
      'adaptive_gate': ctrl.adaptiveGate,
      'trim_silence': ctrl.trimSilence,
      'karaoke_mode': ctrl.karaokeMode,
      'ensemble_mode': ctrl.ensembleMode,
      'include_sfx': ctrl.includeSfx,
      'save_bg': ctrl.saveBg,
      'gen_samples': ctrl.genSamples,
      'enable_sfx_sep': ctrl.enableSfxSep,
      'segment': ctrl.segment,
      'overlap': ctrl.overlap,
      'shifts': ctrl.shifts,
      'gate_threshold_db': ctrl.gateThresholdDb,
      'gate_floor_db': ctrl.gateFloorDb,
      'denoise_strength': ctrl.denoiseStrength,
      'min_vocal_duration': ctrl.minVocalDuration,
      'video_output_mode': ctrl.videoOutputMode,
      'parallel_workers': ctrl.parallelWorkers,
    };

    // 1. Check server health before starting
    final serverOnline = await ctrl.checkServerOnline();
    if (!serverOnline) {
      final detail = widget.backendService?.lastError ?? '';
      ctrl.onJobError(
        'Could not connect to the AI separation server.\n'
        'Make sure the backend is running (http://127.0.0.1:8000).\n'
        '${detail.isNotEmpty ? '$detail\n' : ''}'
        'Click "Retry Server" below to attempt a restart.'
      );
      return;
    }

    // 2. Set processing state on the controller so the RunCard shows progress
    ctrl.prepareForJob();

    try {
      final jobId = await jobManager.startJob(params);
      if (jobId != null) {
        // Start HTTP polling as fallback in case WebSocket events are lost
        ctrl.startPollingJob(jobId);
        ctrl.clearQueue();
      } else {
        ctrl.onJobError('Server did not return a job ID. Check the API server logs.');
      }
    } catch (e) {
      // Catch connection errors and show a user-friendly message
      final msg = e.toString();
      if (msg.contains('SocketException') || msg.contains('Connection refused')) {
        ctrl.onJobError(
          'Could not connect to the AI server.\n'
          'The server may have crashed or is not running.\n'
          'Click "Retry Server" below or restart the app.'
        );
      } else {
        ctrl.onJobError(msg);
      }
    }
  }

  /// Retry starting the backend server and re-check health.
  Future<void> _retryServer() async {
    final backend = widget.backendService;
    if (backend == null) {
      _ctrl.onJobError('Cannot retry — server manager not available. Restart the app.');
      return;
    }

    _ctrl.setStatusText('Starting AI server...', color: AppColors.warning);
    final ok = await backend.retry();
    if (ok) {
      _ctrl.markServerOnline();
      _ctrl.setStatusText('AI server is ready!', color: AppColors.success);
      _ctrl.clearLog();
    } else {
      _ctrl.onJobError(
        'Failed to start the AI server.\n'
        '${backend.lastError ?? "Unknown error"}\n'
        'Check the server log or try restarting the app.'
      );
    }
  }

  void _rebuildTabsIfNeeded() {
    final jobCount = _jobManager.jobs.length;
    final tabCount = 1 + jobCount;
    if (tabCount != _tabController.length) {
      final oldIndex = _tabController.index;
      _tabController.dispose();
      _tabController = TabController(
        length: tabCount,
        vsync: this,
        initialIndex: oldIndex.clamp(0, tabCount - 1),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.instance(context);
    final jobs = _jobManager.jobs;

    return KeyboardListener(
      focusNode: _focusNode,
      autofocus: true,
      onKeyEvent: (event) {
        _ctrl.handleKeyEvent(event);
      },
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Header ──────────────────────────────────────────────
          Padding(
            padding: const EdgeInsets.fromLTRB(32, 32, 32, 0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(l10n.separation, style: AppTextStyles.heading(context)),
                const SizedBox(height: 6),
                Text(l10n.separationSubtitle, style: AppTextStyles.body(context)),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // ── Tab bar ──────────────────────────────────────────────
          TabBar(
            controller: _tabController,
            isScrollable: true,
            labelColor: AppColors.accentPurple,
            unselectedLabelColor: AppColors.textDim,
            indicatorColor: AppColors.accentPurple,
            indicatorWeight: 3,
            labelStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
            unselectedLabelStyle: const TextStyle(fontWeight: FontWeight.w500, fontSize: 13),
            tabs: [
              Tab(
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.add_rounded, size: 16),
                    const SizedBox(width: 6),
                    Text('New Job'),
                  ],
                ),
              ),
              ...jobs.map((job) => Tab(
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    _tabIcon(job.status),
                    const SizedBox(width: 6),
                    Text(job.displayName),
                  ],
                ),
              )),
            ],
          ),

          // ── Tab content ──────────────────────────────────────────
          Expanded(
            child: TabBarView(
              controller: _tabController,
              children: [
                // New Job tab — full configuration + progress
                Padding(
                  padding: const EdgeInsets.all(32),
                  child: SingleChildScrollView(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        FileCard(ctrl: _ctrl),
                        const SizedBox(height: 16),
                        ModelCard(ctrl: _ctrl),
                        const SizedBox(height: 16),
                        SongModeCard(ctrl: _ctrl),
                        const SizedBox(height: 16),
                        OptionsCard(ctrl: _ctrl),
                        const SizedBox(height: 16),
                        DownloadCard(ctrl: _ctrl),
                        const SizedBox(height: 16),
                        // RunCard with progress feedback
                        _RunCardWrapper(
                          ctrl: _ctrl,
                          jobManager: _jobManager,
                          onStartJob: () => _startNewJob(_ctrl, _jobManager),
                          onRetryServer: _retryServer,
                        ),
                        const SizedBox(height: 16),
                        LogCard(ctrl: _ctrl),
                      ],
                    ),
                  ),
                ),

                // Job tabs — each shows progress for a single job
                ...jobs.map((job) => JobTab(
                  key: ValueKey(job.jobId),
                  job: job,
                  jobManager: _jobManager,
                )),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _tabIcon(String status) {
    switch (status) {
      case 'running':
      case 'queued':
        return SizedBox(
          width: 14, height: 14,
          child: CircularProgressIndicator(
            strokeWidth: 2,
            color: AppColors.accentPurple,
          ),
        );
      case 'completed':
        return const Icon(Icons.check_circle_rounded, color: AppColors.success, size: 16);
      case 'error':
        return const Icon(Icons.error_rounded, color: AppColors.error, size: 16);
      case 'cancelled':
        return const Icon(Icons.cancel_rounded, color: AppColors.warning, size: 16);
      default:
        return const Icon(Icons.hourglass_empty_rounded, color: AppColors.textDim, size: 16);
    }
  }
}

/// Run card — start/cancel buttons, progress bar, elapsed/ETA, per-file
/// progress, pipeline visualization, and post-completion actions.
class _RunCardWrapper extends StatelessWidget {
  final SeparationController ctrl;
  final JobManagerController jobManager;
  final VoidCallback onStartJob;
  final VoidCallback? onRetryServer;

  const _RunCardWrapper({
    required this.ctrl,
    required this.jobManager,
    required this.onStartJob,
    this.onRetryServer,
  });

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.instance(context);

    return GlassCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        // ── Action buttons row ──────────────────────────────────
        Row(children: [
          AccentButton(
            label: ctrl.isProcessing ? l10n.loading : l10n.startSeparation,
            icon: ctrl.isProcessing ? Icons.hourglass_top_rounded : Icons.play_arrow_rounded,
            onPressed: ctrl.isProcessing
                ? null
                : (ctrl.files.isNotEmpty ? onStartJob : null),
            enabled: ctrl.files.isNotEmpty && !ctrl.isProcessing,
          ),
          const SizedBox(width: 12),
          if (ctrl.isProcessing)
            DangerButton(label: l10n.cancel, icon: Icons.close_rounded, onPressed: ctrl.cancel),
          const Spacer(),
          // Status badge
          if (ctrl.isProcessing || ctrl.progress > 0 || ctrl.lastError != null)
            StatusBadge(text: ctrl.statusText, color: ctrl.statusColor)
          else if (ctrl.files.isNotEmpty)
            Text('${ctrl.files.length} file(s)', style: AppTextStyles.caption(context)),
        ]),

        // ── Progress bar ────────────────────────────────────────
        if (ctrl.isProcessing || ctrl.progress > 0) ...[
          const SizedBox(height: 12),
          VpProgressBar(value: ctrl.progress),
          const SizedBox(height: 4),
          Row(children: [
            Text('${(ctrl.progress * 100).toInt()}%', style: AppTextStyles.caption(context)),
            if (ctrl.isProcessing && ctrl.etaSeconds > 0) ...[
              const SizedBox(width: 10),
              Icon(Icons.schedule_rounded, size: 12, color: AppColors.textDim),
              const SizedBox(width: 3),
              Text(
                'ETA: ${SeparationController.formatDuration(ctrl.etaSeconds)}',
                style: AppTextStyles.caption(context).copyWith(
                  fontSize: 10,
                  color: AppColors.textDim,
                  fontFamily: 'monospace',
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
            const Spacer(),
            if (ctrl.isProcessing && ctrl.currentFileTotal > 0)
              Text(
                'File ${ctrl.currentFileIndex + 1}/${ctrl.currentFileTotal}',
                style: AppTextStyles.caption(context).copyWith(
                  color: AppColors.accentPurple,
                  fontWeight: FontWeight.w600,
                ),
              ),
          ]),
        ],

        // ── Workflow pipeline ───────────────────────────────────
        if (ctrl.isProcessing || ctrl.progress > 0) ...[
          const SizedBox(height: 16),
          _buildPipeline(context),
        ],

        // ── Elapsed / ETA ───────────────────────────────────────
        if (ctrl.isProcessing && ctrl.elapsedSeconds > 0) ...[
          const SizedBox(height: 14),
          _buildWorkflowDetails(context),
        ],

        // ── Per-file progress list ──────────────────────────────
        if (ctrl.isProcessing && ctrl.files.length > 1) ...[
          const SizedBox(height: 12),
          _buildPerFileProgress(context),
        ],

        // ── Error card ──────────────────────────────────────────
        if (!ctrl.isProcessing && ctrl.lastError != null && ctrl.progress < 1.0) ...[
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppColors.error.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: AppColors.error.withValues(alpha: 0.2)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.error_rounded, color: AppColors.error, size: 20),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        ctrl.lastError!,
                        style: AppTextStyles.body(context).copyWith(
                          color: AppColors.error, fontSize: 12,
                        ),
                      ),
                    ),
                  ],
                ),
                // Retry Server button when server is offline
                if (ctrl.serverOffline && onRetryServer != null) ...[
                  const SizedBox(height: 12),
                  SizedBox(
                    width: double.infinity,
                    child: AccentButton(
                      label: 'Retry Server',
                      icon: Icons.refresh_rounded,
                      onPressed: onRetryServer,
                      compact: true,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],

        // ── Completion feedback ────────────────────────────────
        if (!ctrl.isProcessing && ctrl.progress >= 1.0) ...[
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppColors.success.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: AppColors.success.withValues(alpha: 0.2)),
            ),
            child: Row(
              children: [
                const Icon(Icons.check_circle_rounded, color: AppColors.success, size: 22),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    'Separation Complete',
                    style: AppTextStyles.body(context).copyWith(
                      color: AppColors.success,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                AccentButton(
                  label: 'Open Output',
                  icon: Icons.folder_open_rounded,
                  onPressed: ctrl.openOutputFolder,
                  compact: true,
                ),
              ],
            ),
          ),
        ],

        // ── Prompt when queue is empty ──────────────────────────
        if (ctrl.files.isEmpty && !ctrl.isProcessing && ctrl.progress < 1.0 && ctrl.lastError == null) ...[
          const SizedBox(height: 12),
          Text('Add files above to start a separation',
            style: AppTextStyles.caption(context).copyWith(
              color: AppColors.textDim,
            )),
        ],
      ]),
    );
  }

  // ── Pipeline visualization ──────────────────────────────────────────

  Widget _buildPipeline(BuildContext context) {
    final phases = SeparationController.workflowPhases;
    final current = ctrl.currentPhase;

    int activeIdx = 0;
    for (int i = 0; i < phases.length; i++) {
      if (phases[i].id == current) {
        activeIdx = i;
        break;
      }
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('WORKFLOW', style: AppTextStyles.label(context)),
        const SizedBox(height: 10),
        Row(
          children: List.generate(phases.length, (i) {
            final phase = phases[i];
            final isDone = i < activeIdx;
            final isActive = i == activeIdx;
            final isError = current == 'error' || current == 'cancelled';

            return Expanded(
              child: _buildStep(
                context,
                label: phase.label,
                isDone: isDone,
                isActive: isActive,
                isError: isError && isActive,
                isFirst: i == 0,
                isLast: i == phases.length - 1,
              ),
            );
          }),
        ),
      ],
    );
  }

  Widget _buildStep(
    BuildContext context, {
    required String label,
    required bool isDone,
    required bool isActive,
    required bool isError,
    required bool isFirst,
    required bool isLast,
  }) {
    Color circleColor;
    Color lineColor;
    Widget icon;

    if (isDone) {
      circleColor = AppColors.success;
      lineColor = AppColors.success;
      icon = const Icon(Icons.check_rounded, size: 12, color: Colors.white);
    } else if (isActive && isError) {
      circleColor = AppColors.error;
      lineColor = AppColors.error.withValues(alpha: 0.3);
      icon = const Icon(Icons.close_rounded, size: 12, color: Colors.white);
    } else if (isActive) {
      circleColor = AppColors.accentPurple;
      lineColor = AppColors.glassBorder;
      icon = Container(
        width: 8, height: 8,
        decoration: const BoxDecoration(
          color: AppColors.accentPurple,
          shape: BoxShape.circle,
        ),
      );
    } else {
      circleColor = AppColors.surfaceLight;
      lineColor = AppColors.glassBorder;
      icon = const SizedBox(width: 8, height: 8);
    }

    return IntrinsicHeight(
      child: Row(
        children: [
          Column(
            children: [
              if (!isFirst)
                Container(width: 2, height: 10, color: lineColor)
              else
                const SizedBox(height: 10),
              AnimatedContainer(
                duration: const Duration(milliseconds: 300),
                width: isActive ? 22 : 20,
                height: isActive ? 22 : 20,
                decoration: BoxDecoration(
                  color: circleColor,
                  shape: BoxShape.circle,
                  border: isActive && !isError
                      ? Border.all(color: AppColors.accentPurple.withValues(alpha: 0.4), width: 2)
                      : null,
                  boxShadow: isActive && !isError
                      ? [BoxShadow(color: AppColors.accentPurple.withValues(alpha: 0.3), blurRadius: 6)]
                      : [],
                ),
                child: Center(child: icon),
              ),
              if (!isLast)
                Expanded(child: Container(width: 2, color: lineColor))
              else
                const Expanded(child: SizedBox()),
            ],
          ),
          const SizedBox(width: 6),
          Padding(
            padding: const EdgeInsets.only(bottom: 2),
            child: Text(
              label,
              style: TextStyle(
                fontSize: 9,
                fontWeight: isActive ? FontWeight.w700 : FontWeight.w500,
                color: isDone
                    ? AppColors.success
                    : isActive
                        ? (isError ? AppColors.error : AppColors.accentPurple)
                        : AppColors.textDim,
                letterSpacing: 0.3,
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ── Workflow details (elapsed, ETA, per-file) ────────────────────────

  Widget _buildWorkflowDetails(BuildContext context) {
    final elapsed = SeparationController.formatDuration(ctrl.elapsedSeconds);

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.surfaceLight,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.glassBorder),
      ),
      child: Row(
        children: [
          _detailChip(context, Icons.timer_outlined, 'Elapsed', elapsed),
          const Spacer(),
          if (ctrl.currentFileIndex >= 0)
            _detailChip(
              context,
              Icons.insert_drive_file_outlined,
              'File',
              '${ctrl.currentFileIndex + 1}/${ctrl.currentFileTotal}',
            ),
          if (ctrl.currentFilename != null && ctrl.currentFilename!.isNotEmpty) ...[
            const SizedBox(width: 12),
            Flexible(
              child: Text(
                ctrl.currentFilename!,
                style: AppTextStyles.caption(context).copyWith(
                  fontSize: 10, color: AppColors.textSecondary,
                ),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _detailChip(BuildContext context, IconData icon, String label, String value) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 14, color: AppColors.accentPurple),
        const SizedBox(width: 4),
        Text('$label: ',
          style: TextStyle(fontSize: 10, color: AppColors.textDim, fontWeight: FontWeight.w500)),
        Text(value,
          style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700,
            color: AppColors.textPrimary, fontFamily: 'monospace')),
      ],
    );
  }

  // ── Per-file progress list ──────────────────────────────────────────

  Widget _buildPerFileProgress(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: AppColors.surfaceLight,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.glassBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('FILE PROGRESS', style: AppTextStyles.label(context)),
          const SizedBox(height: 8),
          ...List.generate(ctrl.files.length, (i) {
            final file = ctrl.files[i];
            final state = ctrl.fileStates[i];
            Color dotColor;
            String statusLabel;

            if (state == null) {
              dotColor = AppColors.textDim.withValues(alpha: 0.3);
              statusLabel = 'Waiting';
            } else if (state is double) {
              dotColor = AppColors.accentPurple;
              statusLabel = 'Processing...';
            } else if (state == 'done') {
              dotColor = AppColors.success;
              statusLabel = 'Done \u2713';
            } else if (state == 'error') {
              dotColor = AppColors.error;
              statusLabel = 'Error \u2717';
            } else if (state == 'cancelled') {
              dotColor = AppColors.warning;
              statusLabel = 'Cancelled';
            } else {
              dotColor = AppColors.textDim;
              statusLabel = '';
            }

            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 2),
              child: Row(
                children: [
                  Container(
                    width: 8, height: 8,
                    decoration: BoxDecoration(color: dotColor, shape: BoxShape.circle),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(file.name,
                      style: AppTextStyles.body(context).copyWith(
                        fontSize: 11, color: AppColors.textPrimary,
                      ),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  Text(statusLabel,
                    style: AppTextStyles.caption(context).copyWith(
                      fontSize: 10, color: dotColor, fontWeight: FontWeight.w600,
                    ),
                  ),
                  if (state is double && state > 0) ...[
                    const SizedBox(width: 4),
                    Text('${(state * 100).toInt()}%',
                      style: AppTextStyles.caption(context).copyWith(
                        fontSize: 10, color: AppColors.accentPurple, fontWeight: FontWeight.w600,
                      )),
                  ],
                ],
              ),
            );
          }),
        ],
      ),
    );
  }
}

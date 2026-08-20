import 'package:flutter/material.dart';
import 'package:open_filex/open_filex.dart';
import '../../controllers/job_manager.dart';
import '../../models/separation_job.dart';
import '../../theme.dart';
import '../../l10n/app_localizations.dart';
import '../cards.dart';

/// Widget for displaying a single job tab's progress and results.
class JobTab extends StatelessWidget {
  final SeparationJob job;
  final JobManagerController jobManager;

  const JobTab({super.key, required this.job, required this.jobManager});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.instance(context);

    return Padding(
      padding: const EdgeInsets.all(24),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Header: job name + status + dismiss ────────────────
            Row(children: [
              _statusIcon(job.status),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(job.displayName,
                      style: AppTextStyles.subheading(context)),
                    const SizedBox(height: 2),
                    Text(job.statusText.isNotEmpty ? job.statusText : job.status,
                      style: AppTextStyles.caption(context).copyWith(
                        color: _statusColor(job.status),
                        fontWeight: FontWeight.w600,
                      )),
                  ],
                ),
              ),
              if (job.isRunning)
                DangerButton(
                  label: l10n.cancel,
                  icon: Icons.close_rounded,
                  onPressed: () => jobManager.cancelJob(job.jobId),
                ),
              if (job.isTerminal) ...[
                const SizedBox(width: 8),
                AccentButton(
                  label: 'Dismiss',
                  icon: Icons.close_rounded,
                  compact: true,
                  onPressed: () => jobManager.dismissJob(job.jobId),
                ),
              ],
            ]),
            const SizedBox(height: 20),

            // ── Progress bar ───────────────────────────────────────
            if (job.totalProgress > 0 || job.isRunning) ...[
              VpProgressBar(value: job.totalProgress),
              const SizedBox(height: 6),
              Row(children: [
                Text('${(job.totalProgress * 100).toInt()}%',
                  style: AppTextStyles.caption(context)),
                if (job.currentFile >= 0 && job.totalFiles > 0) ...[
                  const Spacer(),
                  Text('File ${job.currentFile + 1}/${job.totalFiles}',
                    style: AppTextStyles.caption(context).copyWith(
                      color: AppColors.accentPurple,
                      fontWeight: FontWeight.w600,
                    )),
                ],
              ]),
              const SizedBox(height: 16),
            ],

            // ── File list with per-file progress ───────────────────
            _buildFileList(context),

            const SizedBox(height: 16),

            // ── Completion result ──────────────────────────────────
            if (job.isCompleted && job.outputPath != null)
              _buildCompletionCard(context),

            // ── Error message ──────────────────────────────────────
            if (job.isError && job.error != null)
              _buildErrorCard(context, job.error!),
          ],
        ),
      ),
    );
  }

  Widget _buildFileList(BuildContext context) {
    final states = job.progress;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.surfaceLight,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.glassBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Text('FILES', style: AppTextStyles.label(context)),
            const Spacer(),
            Text('${job.files.length} file(s)',
              style: AppTextStyles.caption(context)),
          ]),
          const SizedBox(height: 8),
          ...List.generate(job.files.length, (i) {
            final fileName = job.files[i].split(RegExp(r'[/\\]')).last;
            final state = states[i];
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
              statusLabel = 'Done ✓';
            } else if (state == 'error') {
              dotColor = AppColors.error;
              statusLabel = 'Error ✗';
            } else if (state == 'cancelled') {
              dotColor = AppColors.warning;
              statusLabel = 'Cancelled';
            } else {
              dotColor = AppColors.textDim;
              statusLabel = '';
            }

            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 3),
              child: Row(
                children: [
                  Container(
                    width: 8, height: 8,
                    decoration: BoxDecoration(
                      color: dotColor, shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(fileName,
                      style: AppTextStyles.body(context).copyWith(
                        fontSize: 12,
                        color: AppColors.textPrimary,
                      ),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  Text(statusLabel,
                    style: AppTextStyles.caption(context).copyWith(
                      fontSize: 10,
                      color: dotColor,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  if (state is double && state > 0) ...[
                    const SizedBox(width: 4),
                    Text('${(state * 100).toInt()}%',
                      style: AppTextStyles.caption(context).copyWith(
                        fontSize: 10, color: AppColors.accentPurple,
                        fontWeight: FontWeight.w600,
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

  Widget _buildCompletionCard(BuildContext context) {
    return Container(
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
            child: Text('Separation complete — ${job.files.length} file(s) processed',
              style: AppTextStyles.body(context).copyWith(
                color: AppColors.success,
                fontWeight: FontWeight.w600,
              )),
          ),            AccentButton(
              label: 'Open Output',
              icon: Icons.folder_open_rounded,
              compact: true,
              onPressed: () => _openOutputFolder(job),
            ),
        ],
      ),
    );
  }

  Widget _buildErrorCard(BuildContext context, String error) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.error.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.error.withValues(alpha: 0.2)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.error_rounded, color: AppColors.error, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Text(error,
              style: AppTextStyles.body(context).copyWith(
                color: AppColors.error, fontSize: 12,
              )),
          ),
        ],
      ),
    );
  }

  Widget _statusIcon(String status) {
    switch (status) {
      case 'running':
      case 'queued':
        return SizedBox(
          width: 18, height: 18,
          child: CircularProgressIndicator(
            strokeWidth: 2,
            color: AppColors.accentPurple,
          ),
        );
      case 'completed':
        return const Icon(Icons.check_circle_rounded, color: AppColors.success, size: 22);
      case 'error':
        return const Icon(Icons.error_rounded, color: AppColors.error, size: 22);
      case 'cancelled':
        return const Icon(Icons.cancel_rounded, color: AppColors.warning, size: 22);
      default:
        return const Icon(Icons.hourglass_empty_rounded, color: AppColors.textDim, size: 22);
    }
  }

  Color _statusColor(String status) {
    switch (status) {
      case 'running': return AppColors.accentPurple;
      case 'queued': return AppColors.warning;
      case 'completed': return AppColors.success;
      case 'error': return AppColors.error;
      case 'cancelled': return AppColors.warning;
      default: return AppColors.textDim;
    }
  }

  void _openOutputFolder(SeparationJob job) {
    if (job.outputPath != null && job.outputPath!.isNotEmpty) {
      final folder = job.outputPath!.contains(RegExp(r'[/\\]'))
          ? job.outputPath!.substring(0, job.outputPath!.lastIndexOf(RegExp(r'[/\\]')) + 1)
          : job.outputPath!;
      try {
        OpenFilex.open(folder);
      } catch (_) {
        debugPrint('Could not open: $folder');
      }
    }
  }
}

import 'package:flutter/material.dart';
import '../../controllers/separation_controller.dart';
import '../../l10n/app_localizations.dart';
import '../../theme.dart';
import '../cards.dart';

/// Download progress card — shown while a URL download is active or completed.
class DownloadCard extends StatelessWidget {
  final SeparationController ctrl;
  const DownloadCard({super.key, required this.ctrl});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.instance(context);
    return ListenableBuilder(
      listenable: ctrl,
      builder: (context, _) {
        if (!ctrl.isDownloading && ctrl.downloadStatus.isEmpty) {
          return const SizedBox.shrink();
        }
        return GlassCard(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Text(l10n.download, style: AppTextStyles.label(context)),
              const Spacer(),
              if (ctrl.isDownloading)
                GhostButton(label: l10n.cancel, icon: Icons.close_rounded, onPressed: ctrl.cancelDownload)
              else if (ctrl.lastUrl != null)
                GhostButton(label: l10n.retry, icon: Icons.refresh_rounded, onPressed: ctrl.retryDownload),
            ]),
            if (ctrl.isDownloading) ...[
              const SizedBox(height: 8),
              VpProgressBar(value: (ctrl.downloadProgress / 100).clamp(0.0, 1.0)),
              const SizedBox(height: 4),
              Text(
                '${ctrl.downloadStatus} \u2014 ${ctrl.downloadProgress.toStringAsFixed(0)}%',
                style: AppTextStyles.caption(context),
              ),
            ] else ...[
              const SizedBox(height: 8),
              StatusBadge(
                text: ctrl.downloadStatus,
                color: ctrl.downloadStatus == l10n.error ? AppColors.error : AppColors.warning,
              ),
            ],
          ]),
        );
      },
    );
  }
}

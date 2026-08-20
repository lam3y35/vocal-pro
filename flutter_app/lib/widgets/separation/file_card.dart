import 'package:flutter/material.dart';
import 'package:desktop_drop/desktop_drop.dart';
import '../../controllers/separation_controller.dart';
import '../../l10n/app_localizations.dart';
import '../../theme.dart';
import '../cards.dart';

/// File management card — queue, drag-drop, URL dialog, browse, output folder.
/// Displays per-file progress status icons.
class FileCard extends StatelessWidget {
  final SeparationController ctrl;
  const FileCard({super.key, required this.ctrl});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.instance(context);
    return ListenableBuilder(
      listenable: ctrl,
      builder: (context, _) => GlassCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          SectionHeader(
            title: l10n.sourceFiles,
            subtitle: l10n.sourceFilesSubtitle,
            trailing: Row(mainAxisSize: MainAxisSize.min, children: [
              GhostButton(
                label: l10n.url,
                icon: Icons.link_rounded,
                onPressed: () => _showUrlDialog(context),
                enabled: !ctrl.isDownloading,
              ),
              const SizedBox(width: 6),
              GhostButton(
                label: l10n.get('browse'),
                icon: Icons.folder_open_rounded,
                onPressed: ctrl.browseFiles,
              ),
              if (ctrl.files.isNotEmpty) ...[
                const SizedBox(width: 6),
                DangerButton(
                  label: l10n.clear,
                  icon: Icons.delete_outline_rounded,
                  onPressed: ctrl.clearQueue,
                ),
              ],
            ]),
          ),
          if (ctrl.files.isEmpty)
            DropTarget(
              onDragDone: (details) {
                for (final file in details.files) {
                  final ext = file.name.split('.').last.toLowerCase();
                  if (['mp4', 'mkv', 'avi', 'mov', 'flv', 'mp3', 'wav', 'flac', 'ogg'].contains(ext)) {
                    ctrl.addFileFromDrop(file.path, file.name);
                  } else {
                    ctrl.addLogLine('\u26A0\uFE0F Skipping: ${file.name} (unsupported format)');
                  }
                }
              },
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(vertical: 32),
                decoration: BoxDecoration(
                  color: AppColors.surfaceLight,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppColors.glassBorder),
                ),
                child: Column(children: [
                  Icon(Icons.cloud_upload_rounded, size: 40, color: AppColors.textDim),
                  const SizedBox(height: 8),
                  Text(l10n.dropFilesHint, style: AppTextStyles.body(context)),
                  Text(l10n.supportedFormats, style: AppTextStyles.caption(context)),
                  const SizedBox(height: 4),
                  Text(l10n.shortcuts, style: AppTextStyles.caption(context)),
                ]),
              ),
            )
          else ...[
            const SizedBox(height: 8),
            ...List.generate(ctrl.files.length, (i) => _buildFileRow(context, i)),
            const SizedBox(height: 4),
            Row(children: [
              Text('${ctrl.files.length} ${l10n.filesInQueue}', style: AppTextStyles.caption(context)),
              const Spacer(),
              if (ctrl.detectedBpm != null || ctrl.detectedKey != null)
                Row(children: [
                  if (ctrl.detectedBpm != null)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: AppColors.info.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        '\u2669 ${ctrl.detectedBpm} BPM',
                        style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: AppColors.info),
                      ),
                    ),
                  if (ctrl.detectedKey != null) ...[
                    const SizedBox(width: 6),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: AppColors.success.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        '\uD83C\uDFB5 ${ctrl.detectedKey}',
                        style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: AppColors.success),
                      ),
                    ),
                  ],
                ]),
            ]),
            const SizedBox(height: 8),
            Row(children: [
              GhostButton(
                label: '\uD83D\uDCC2 ${l10n.outputFolder}',
                icon: Icons.folder_rounded,
                onPressed: ctrl.browseOutputDir,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  ctrl.outputDir ?? l10n.defaultOutput,
                  style: AppTextStyles.caption(context),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              const SizedBox(width: 4),
              if (ctrl.outputDir != null)
                GhostButton(
                  label: l10n.get('reveal'),
                  icon: Icons.open_in_new_rounded,
                  compact: true,
                  onPressed: () => _revealFolder(context, ctrl.outputDir!),
                ),
            ]),
          ],
        ]),
      ),
    );
  }

  Widget _buildFileRow(BuildContext context, int index) {
    final file = ctrl.files[index];
    final fileState = ctrl.fileStates[index];

    // Determine status icon and color
    Widget? statusIcon;
    Color? statusColor;

    if (fileState == null) {
      // Waiting — no icon
    } else if (fileState is double) {
      if (fileState == 0.0) {
        // Started but no progress yet
        statusIcon = SizedBox(
          width: 14,
          height: 14,
          child: CircularProgressIndicator(
            strokeWidth: 2,
            color: AppColors.warning,
          ),
        );
        statusColor = AppColors.warning;
      } else {
        // In progress
        statusIcon = SizedBox(
          width: 14,
          height: 14,
          child: CircularProgressIndicator(
            strokeWidth: 2,
            value: fileState,
            color: AppColors.accentPurple,
          ),
        );
        statusColor = AppColors.accentPurple;
      }
    } else if (fileState == 'done') {
      statusIcon = const Icon(Icons.check_circle_rounded, size: 16, color: AppColors.success);
      statusColor = AppColors.success;
    } else if (fileState == 'error') {
      statusIcon = const Icon(Icons.error_rounded, size: 16, color: AppColors.error);
      statusColor = AppColors.error;
    } else if (fileState == 'cancelled') {
      statusIcon = const Icon(Icons.cancel_rounded, size: 16, color: AppColors.warning);
      statusColor = AppColors.warning;
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 4),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: statusColor?.withValues(alpha: 0.08) ?? AppColors.surfaceLight,
        borderRadius: BorderRadius.circular(8),
        border: statusColor != null
            ? Border.all(color: statusColor.withValues(alpha: 0.2))
            : null,
      ),
      child: Row(children: [
        if (statusIcon != null) ...[
          statusIcon,
          const SizedBox(width: 8),
        ] else ...[
          Icon(Icons.audiotrack_rounded, size: 16, color: AppColors.accentPurple),
          const SizedBox(width: 8),
        ],
        Expanded(
          child: Text(
            file.name,
            style: AppTextStyles.body(context).copyWith(
              color: AppColors.textPrimary,
              fontSize: 13,
            ),
            overflow: TextOverflow.ellipsis,
          ),
        ),
        // Show progress percentage for in-progress files
        if (fileState is double && fileState > 0)
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: Text(
              '${(fileState * 100).toInt()}%',
              style: AppTextStyles.caption(context).copyWith(
                color: AppColors.accentPurple,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        InkWell(
          onTap: () => ctrl.removeFile(index),
          child: Icon(Icons.close_rounded, size: 16, color: AppColors.textDim),
        ),
      ]),
    );
  }

  void _showUrlDialog(BuildContext context) {
    final l10n = AppLocalizations.instance(context);
    ctrl.urlController.text = ctrl.lastUrl ?? '';
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Text(l10n.loadFromUrl, style: AppTextStyles.subheading(context)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(l10n.pasteUrlHint, style: AppTextStyles.body(context)),
            const SizedBox(height: 12),
            TextField(
              controller: ctrl.urlController,
              decoration: InputDecoration(
                hintText: 'https://example.com/song.mp3',
                hintStyle: AppTextStyles.caption(context),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                  borderSide: const BorderSide(color: AppColors.glassBorder),
                ),
                filled: true,
                fillColor: AppColors.surfaceLight,
              ),
              style: AppTextStyles.mono(context),
            ),
          ],
        ),
        actions: [
          GhostButton(label: l10n.cancel, onPressed: () => Navigator.pop(ctx)),
          const SizedBox(width: 8),
          AccentButton(
            label: l10n.download,
            icon: Icons.download_rounded,
            onPressed: () {
              Navigator.pop(ctx);
              ctrl.downloadFromUrl();
            },
          ),
        ],
      ),
    );
  }

  void _revealFolder(BuildContext context, String path) {
    ctrl.addLogLine('\uD83D\uDCC2 $path');
  }
}

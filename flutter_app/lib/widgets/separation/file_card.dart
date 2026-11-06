import 'package:flutter/material.dart';
import 'package:desktop_drop/desktop_drop.dart';
import '../../controllers/separation_controller.dart';
import '../../l10n/app_localizations.dart';
import '../../theme.dart';
import '../cards.dart';

/// File management card — queue, drag-drop, URL dialog, browse, output folder.
/// Displays per-file progress status icons.
class FileCard extends StatefulWidget {
  final SeparationController ctrl;
  const FileCard({super.key, required this.ctrl});

  @override
  State<FileCard> createState() => _FileCardState();
}

class _FileCardState extends State<FileCard> {
  bool _isDragging = false;

  static const _supportedExts = {
    'mp3', 'wav', 'flac', 'ogg', 'm4a', 'aac', 'wma', 'aiff',
    'mp4', 'mkv', 'avi', 'mov', 'flv', 'webm', 'm4v', '3gp', 'wmv',
  };

  void _onFilesDropped(List<dynamic> files) {
    for (final file in files) {
      final rawPath = file.path as String;
      var rawName = (file.name as String?) ?? '';
      if (rawName.isEmpty) {
        rawName = rawPath.split(RegExp(r'[/\]')).last;
      }
      final ext = rawName.contains('.') ? rawName.split('.').last.toLowerCase() : '';
      if (_supportedExts.contains(ext)) {
        widget.ctrl.addFileFromDrop(rawPath, rawName);
      } else {
        widget.ctrl.addLogLine('\u26A0\uFE0F Skipping: $rawName (unsupported format)');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.instance(context);
    final ctrl = widget.ctrl;
    return ListenableBuilder(
      listenable: ctrl,
      builder: (context, _) => DropTarget(
        onDragEntered: (_) => setState(() => _isDragging = true),
        onDragExited: (_) => setState(() => _isDragging = false),
        onDragDone: (details) {
          setState(() => _isDragging = false);
          _onFilesDropped(details.files);
        },
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            border: _isDragging
                ? Border.all(color: AppColors.accentPurple, width: 2)
                : null,
            boxShadow: _isDragging
                ? [
                    BoxShadow(
                      color: AppColors.accentPurple.withValues(alpha: 0.35),
                      blurRadius: 16,
                      spreadRadius: 2,
                    ),
                  ]
                : null,
          ),
          child: GlassCard(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              SectionHeader(
                title: l10n.sourceFiles,
                subtitle: _isDragging ? 'Drop files here to add to queue' : l10n.sourceFilesSubtitle,
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
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(vertical: 32),
                  decoration: BoxDecoration(
                    color: _isDragging
                        ? AppColors.accentPurple.withValues(alpha: 0.15)
                        : AppColors.surfaceLight,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: _isDragging ? AppColors.accentPurple : AppColors.glassBorder,
                      width: _isDragging ? 2 : 1,
                    ),
                  ),
                  child: Column(children: [
                    Icon(
                      _isDragging ? Icons.file_download_rounded : Icons.cloud_upload_rounded,
                      size: 40,
                      color: _isDragging ? AppColors.accentPurple : AppColors.textDim,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      _isDragging ? 'Release to add files' : l10n.dropFilesHint,
                      style: AppTextStyles.body(context).copyWith(
                        color: _isDragging ? AppColors.accentPurple : null,
                        fontWeight: _isDragging ? FontWeight.w600 : null,
                      ),
                    ),
                    Text(l10n.supportedFormats, style: AppTextStyles.caption(context)),
                    const SizedBox(height: 4),
                    Text(l10n.shortcuts, style: AppTextStyles.caption(context)),
                  ]),
                )
              else ...[
                const SizedBox(height: 8),
                ...List.generate(ctrl.files.length, (i) => _buildFileRow(context, i)),
                const SizedBox(height: 8),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  decoration: BoxDecoration(
                    color: _isDragging
                        ? AppColors.accentPurple.withValues(alpha: 0.15)
                        : AppColors.surfaceLight.withValues(alpha: 0.5),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: _isDragging ? AppColors.accentPurple : AppColors.glassBorder,
                    ),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(
                        Icons.add_circle_outline_rounded,
                        size: 16,
                        color: _isDragging ? AppColors.accentPurple : AppColors.textDim,
                      ),
                      const SizedBox(width: 8),
                      Text(
                        _isDragging ? 'Release to add more files' : 'Drop more files here to add to queue',
                        style: AppTextStyles.caption(context).copyWith(
                          color: _isDragging ? AppColors.accentPurple : AppColors.textDim,
                          fontWeight: _isDragging ? FontWeight.w600 : null,
                        ),
                      ),
                    ],
                  ),
                ),
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
        ),
      ),
    );
  }

  Widget _buildFileRow(BuildContext context, int index) {
    final ctrl = widget.ctrl;
    final file = ctrl.files[index];
    final fileState = ctrl.fileStates[index];
    final isSelected = ctrl.activeAudioPath == file.path;

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

    return InkWell(
      onTap: () => ctrl.selectFileForPreview(index),
      borderRadius: BorderRadius.circular(8),
      child: Container(
        margin: const EdgeInsets.only(bottom: 4),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: isSelected
              ? AppColors.accentPurple.withValues(alpha: 0.15)
              : (statusColor?.withValues(alpha: 0.08) ?? AppColors.surfaceLight),
          borderRadius: BorderRadius.circular(8),
          border: isSelected
              ? Border.all(color: AppColors.accentPurple.withValues(alpha: 0.5))
              : (statusColor != null
                  ? Border.all(color: statusColor.withValues(alpha: 0.2))
                  : null),
        ),
        child: Row(children: [
          if (statusIcon != null) ...[
            statusIcon,
            const SizedBox(width: 8),
          ] else ...[
            Icon(
              isSelected ? Icons.play_circle_fill_rounded : Icons.audiotrack_rounded,
              size: 16,
              color: isSelected ? AppColors.accentPurple : AppColors.textDim,
            ),
            const SizedBox(width: 8),
          ],
          Expanded(
            child: Text(
              file.name,
              style: AppTextStyles.body(context).copyWith(
                color: AppColors.textPrimary,
                fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
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
      ),
    );
  }

  void _showUrlDialog(BuildContext context) {
    final ctrl = widget.ctrl;
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
    widget.ctrl.addLogLine('\uD83D\uDCC2 $path');
  }
}

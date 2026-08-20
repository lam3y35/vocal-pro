import 'package:flutter/material.dart';
import '../theme.dart';
import '../widgets/cards.dart';
import '../services/api_service.dart';
import '../l10n/app_localizations.dart';
import '../l10n/locale_provider.dart';

/// History screen – separation and download history.
class HistoryScreen extends StatefulWidget {
  final ApiService api;
  final LocaleProvider localeProvider;
  const HistoryScreen({super.key, required this.api, required this.localeProvider});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  List<dynamic> _sepHistory = [];
  List<dynamic> _dlHistory = [];
  bool _loading = true;
  bool _showSeparation = true;

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  Future<void> _loadHistory() async {
    setState(() => _loading = true);
    try {
      final sep = await widget.api.getHistory();
      final dl = await widget.api.getDownloadHistory();
      setState(() {
        _sepHistory = (sep['history'] as List?) ?? [];
        _dlHistory = (dl['history'] as List?) ?? [];
        _loading = false;
      });
    } catch (e) {
      setState(() => _loading = false);
    }
  }

  Future<void> _clearSepHistory() async {
    final l10n = AppLocalizations.instance(context);
    try {
      await widget.api.clearSepHistory();
      setState(() => _sepHistory = []);
      if (mounted) _snack('\u2705', l10n.clearAllHistory, AppColors.success);
    } catch (e) {
      if (mounted) _snack('\u274c', '$e', AppColors.error);
    }
  }

  Future<void> _clearDlHistory() async {
    final l10n = AppLocalizations.instance(context);
    try {
      await widget.api.clearDownloadHistory();
      setState(() => _dlHistory = []);
      if (mounted) _snack('\u2705', l10n.clearAllHistory, AppColors.success);
    } catch (e) {
      if (mounted) _snack('\u274c', '$e', AppColors.error);
    }
  }

  void _snack(String icon, String msg, Color color) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text('$icon $msg'),
      backgroundColor: color,
      behavior: SnackBarBehavior.floating,
    ));
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.instance(context);
    return Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(l10n.history, style: AppTextStyles.heading(context)),
              const Spacer(),
              _buildToggleChip(l10n.separations, _showSeparation, () => setState(() => _showSeparation = true)),
              const SizedBox(width: 8),
              _buildToggleChip(l10n.downloads, !_showSeparation, () => setState(() => _showSeparation = false)),
              const SizedBox(width: 12),
              GhostButton(label: l10n.refresh, icon: Icons.refresh_rounded, onPressed: _loadHistory),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            _showSeparation ? l10n.sepHistorySubtitle : l10n.dlHistorySubtitle,
            style: AppTextStyles.body(context),
          ),
          const SizedBox(height: 24),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator(color: AppColors.accentPurple))
                : _showSeparation ? _buildSepHistory(l10n) : _buildDlHistory(l10n),
          ),
        ],
      ),
    );
  }

  Widget _buildToggleChip(String label, bool selected, VoidCallback onTap) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        decoration: BoxDecoration(
          color: selected
              ? AppColors.accentPurple.withValues(alpha: 0.15)
              : AppColors.surface,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: selected
                ? AppColors.accentPurple.withValues(alpha: 0.3)
                : AppColors.glassBorder,
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w600,
            color: selected ? AppColors.accentPurple : AppColors.textDim,
          ),
        ),
      ),
    );
  }

  Widget _buildSepHistory(AppLocalizations l10n) {
    if (_sepHistory.isEmpty) {
      return GlassCard(
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.history_rounded, size: 48, color: AppColors.textDim),
              const SizedBox(height: 12),
              Text(l10n.noSepHistory, style: AppTextStyles.body(context)),
              Text(l10n.runSeparationToSee, style: AppTextStyles.caption(context)),
            ],
          ),
        ),
      );
    }
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          child: Row(
            children: [
              _headerCell(l10n.get('status'), 6),
              _headerCell(l10n.files, 20),
              _headerCell(l10n.model, 12),
              _headerCell(l10n.outputFolder, 10),
              _headerCell(l10n.get('date'), 13),
              _headerCell('', 1),
            ],
          ),
        ),
        const SizedBox(height: 4),
        Expanded(
          child: GlassCard(
            padding: const EdgeInsets.all(12),
            child: ListView.builder(
              itemCount: _sepHistory.length,
              itemBuilder: (ctx, i) => _buildSepHistoryRow(
                _sepHistory[_sepHistory.length - 1 - i],
                l10n,
              ),
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.only(top: 8),
          child: Row(
            children: [
              DangerButton(
                label: l10n.clearAllHistory,
                icon: Icons.delete_sweep_rounded,
                onPressed: _clearSepHistory,
              ),
              const Spacer(),
              Text('${_sepHistory.length} ${l10n.entries}', style: AppTextStyles.caption(context)),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildSepHistoryRow(Map<String, dynamic> entry, AppLocalizations l10n) {
    final status = entry['status'] ?? 'unknown';
    final files = (entry['files'] as List?) ?? [];
    final model = entry['model'] ?? '';
    final timestamp = entry['timestamp'] ?? '';
    final folder = entry['output_folder'] ?? '';
    Color statusColor;
    IconData statusIcon;
    switch (status) {
      case 'success':
        statusColor = AppColors.success;
        statusIcon = Icons.check_circle_rounded;
        break;
      case 'error':
        statusColor = AppColors.error;
        statusIcon = Icons.error_rounded;
        break;
      case 'cancelled':
        statusColor = AppColors.warning;
        statusIcon = Icons.cancel_rounded;
        break;
      default:
        statusColor = AppColors.textDim;
        statusIcon = Icons.help_rounded;
    }
    final fileNames = files.take(3).join(', ');
    final extra = files.length > 3 ? ' \u2026(+${files.length - 3})' : '';
    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
      decoration: BoxDecoration(
        color: AppColors.surfaceLight,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          SizedBox(
            width: 60,
            child: Icon(statusIcon, size: 18, color: statusColor),
          ),
          SizedBox(
            width: 200,
            child: Text(
              '$fileNames$extra',
              style: AppTextStyles.body(context).copyWith(color: AppColors.textPrimary, fontSize: 12),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          SizedBox(
            width: 120,
            child: Text(model, style: AppTextStyles.caption(context), overflow: TextOverflow.ellipsis),
          ),
          Expanded(
            child: Text(folder, style: AppTextStyles.caption(context), overflow: TextOverflow.ellipsis),
          ),
          SizedBox(
            width: 130,
            child: Text(timestamp, style: AppTextStyles.caption(context)),
          ),
          SizedBox(
            width: 50,
            child: status == 'success' && folder.isNotEmpty
                ? Tooltip(
                    message: l10n.rerun,
                    child: Material(
                      color: Colors.transparent,
                      child: InkWell(
                        onTap: () => _reRunSeparation(entry, l10n),
                        borderRadius: BorderRadius.circular(8),
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
                          decoration: BoxDecoration(
                            color: AppColors.accentPurple.withValues(alpha: 0.12),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: AppColors.accentPurple.withValues(alpha: 0.3)),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(Icons.refresh_rounded, size: 14, color: AppColors.accentPurple),
                              const SizedBox(width: 2),
                              Text('\u21bb', style: TextStyle(fontSize: 12, color: AppColors.accentPurple, fontWeight: FontWeight.w600)),
                            ],
                          ),
                        ),
                      ),
                    ),
                  )
                : const SizedBox.shrink(),
          ),
        ],
      ),
    );
  }

  Widget _buildDlHistory(AppLocalizations l10n) {
    if (_dlHistory.isEmpty) {
      return GlassCard(
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.download_rounded, size: 48, color: AppColors.textDim),
              const SizedBox(height: 12),
              Text(l10n.noDlHistory, style: AppTextStyles.body(context)),
              Text(l10n.get('downloadFileToSee'), style: AppTextStyles.caption(context)),
            ],
          ),
        ),
      );
    }
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          child: Row(
            children: [
              _headerCell(l10n.get('status'), 6),
              _headerCell(l10n.files, 25),
              _headerCell('Size', 8),
              _headerCell(l10n.get('date'), 13),
              _headerCell('URL', 10),
            ],
          ),
        ),
        const SizedBox(height: 4),
        Expanded(
          child: GlassCard(
            padding: const EdgeInsets.all(12),
            child: ListView.builder(
              itemCount: _dlHistory.length,
              itemBuilder: (ctx, i) => _buildDlHistoryRow(
                _dlHistory[_dlHistory.length - 1 - i],
                l10n,
              ),
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.only(top: 8),
          child: Row(
            children: [
              DangerButton(
                label: l10n.clearAllHistory,
                icon: Icons.delete_sweep_rounded,
                onPressed: _clearDlHistory,
              ),
              const Spacer(),
              Text('${_dlHistory.length} ${l10n.entries}', style: AppTextStyles.caption(context)),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildDlHistoryRow(Map<String, dynamic> entry, AppLocalizations l10n) {
    final status = entry['status'] ?? 'unknown';
    final filename = entry['filename'] ?? '';
    final size = entry['size'] ?? '';
    final timestamp = entry['timestamp'] ?? '';
    final url = entry['url'] ?? '';
    Color statusColor;
    IconData statusIcon;
    switch (status) {
      case 'success':
        statusColor = AppColors.success;
        statusIcon = Icons.check_circle_rounded;
        break;
      case 'error':
        statusColor = AppColors.error;
        statusIcon = Icons.error_rounded;
        break;
      case 'cancelled':
        statusColor = AppColors.warning;
        statusIcon = Icons.cancel_rounded;
        break;
      default:
        statusColor = AppColors.textDim;
        statusIcon = Icons.help_rounded;
    }
    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
      decoration: BoxDecoration(
        color: AppColors.surfaceLight,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        children: [
          SizedBox(width: 60, child: Icon(statusIcon, size: 18, color: statusColor)),
          SizedBox(
            width: 250,
            child: Text(filename, style: AppTextStyles.body(context).copyWith(color: AppColors.textPrimary, fontSize: 12), overflow: TextOverflow.ellipsis),
          ),
          SizedBox(width: 80, child: Text(size, style: AppTextStyles.caption(context))),
          SizedBox(width: 130, child: Text(timestamp, style: AppTextStyles.caption(context))),
          Expanded(child: Text(url, style: AppTextStyles.caption(context), overflow: TextOverflow.ellipsis)),
        ],
      ),
    );
  }

  void _reRunSeparation(Map<String, dynamic> entry, AppLocalizations l10n) {
    final filePaths = entry['full_paths'] as List? ?? [];
    if (filePaths.isEmpty) {
      _snack('\u26a0\ufe0f', l10n.noFilePathsInHistory, AppColors.warning);
      return;
    }
    final model = entry['model'] ?? 'htdemucs_ft';
    final folder = entry['output_folder'] ?? '';
    _snack('\ud83d\udd04', '${filePaths.length} ${l10n.files.toLowerCase()}: $model', AppColors.accentPurple);
    widget.api.rerunSeparation(filePaths: filePaths.cast<String>(), outputDir: folder, modelName: model);
  }

  Widget _headerCell(String text, int flex) => Expanded(
        flex: flex,
        child: Text(text, style: AppTextStyles.label(context), overflow: TextOverflow.ellipsis),
      );
}

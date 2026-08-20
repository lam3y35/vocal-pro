import 'dart:async';

import 'package:flutter/material.dart';
import '../theme.dart';
import '../widgets/cards.dart';
import '../services/api_service.dart';
import '../l10n/app_localizations.dart';
import '../l10n/locale_provider.dart';

/// Results / Stem Mixer screen.
class ResultsScreen extends StatefulWidget {
  final ApiService api;
  final LocaleProvider localeProvider;
  const ResultsScreen({super.key, required this.api, required this.localeProvider});

  @override
  State<ResultsScreen> createState() => _ResultsScreenState();
}

class _ResultsScreenState extends State<ResultsScreen> {
  List<dynamic> _outputs = [];
  bool _loading = true;
  String? _selectedFolder;
  List<_StemInfo> _stems = [];
  Map<String, double> _stemVolumes = {};
  double _masterVolume = 1.0;
  bool _isPreviewing = false;
  bool _isPlaying = false;
  double _previewPos = 0;
  Timer? _previewTimer;

  static const _stemColors = [
    Color(0xFF7C3AED),
    Color(0xFF22C55E),
    Color(0xFFF59E0B),
    Color(0xFFEF4444),
    Color(0xFF3B82F6),
    Color(0xFFEC4899),
  ];

  @override
  void initState() {
    super.initState();
    _loadOutputs();
  }

  @override
  void dispose() {
    _previewTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadOutputs() async {
    setState(() => _loading = true);
    try {
      final resp = await widget.api.getOutputs();
      setState(() {
        _outputs = resp['outputs'] ?? [];
        _loading = false;
      });
    } catch (e) {
      setState(() => _loading = false);
    }
  }

  Future<void> _selectFolder(String folderName) async {
    setState(() {
      _selectedFolder = folderName;
      _stems = [];
      _stemVolumes = {};
      _isPreviewing = false;
      _isPlaying = false;
    });
    _previewTimer?.cancel();
    try {
      final resp = await widget.api.getStems(folderName);
      final stemsData = resp['stems'] ?? [];
      setState(() {
        _stems = stemsData
            .map<Map<String, dynamic>>((s) => s as Map<String, dynamic>)
            .toList()
            .asMap()
            .entries
            .map((e) => _StemInfo(
                  key: e.value['key'] ?? '',
                  label: e.value['label'] ?? '',
                  filename: e.value['filename'] ?? '',
                  path: e.value['path'] ?? '',
                  sizeMb: (e.value['size_mb'] as num?)?.toDouble() ?? 0,
                  colorIndex: e.key,
                ))
            .toList();
        for (final s in _stems) {
          _stemVolumes[s.key] = 1.0;
        }
      });
    } catch (_) {}
  }

  Future<void> _previewMix() async {
    if (_selectedFolder == null || _stems.isEmpty) return;
    final l10n = AppLocalizations.instance(context);
    setState(() => _isPreviewing = true);
    try {
      await widget.api.stemPreview(
        folderName: _selectedFolder!,
        volumes: _stemVolumes,
        masterVolume: _masterVolume,
      );
      setState(() {
        _isPreviewing = false;
        _isPlaying = true;
        _previewPos = 0;
      });
      _previewTimer = Timer.periodic(const Duration(milliseconds: 200), (_) {
        if (!mounted) return;
        setState(() {
          _previewPos += 0.2;
          if (_previewPos >= 15) {
            _previewPos = 0;
            _stopPreview();
          }
        });
      });
    } catch (e) {
      setState(() => _isPreviewing = false);
      if (mounted) _showSnack(l10n.error, e.toString(), AppColors.error);
    }
  }

  void _stopPreview() {
    _previewTimer?.cancel();
    setState(() {
      _isPlaying = false;
      _isPreviewing = false;
      _previewPos = 0;
    });
  }

  Future<void> _exportMix() async {
    if (_selectedFolder == null || _stems.isEmpty) return;
    final l10n = AppLocalizations.instance(context);
    try {
      final resp = await widget.api.stemExport(
        folderName: _selectedFolder!,
        volumes: _stemVolumes,
        masterVolume: _masterVolume,
        outputFormat: 'wav',
      );
      if (resp['status'] == 'ok' && mounted) {
        _showSnack('\u2705', '${resp["filename"]} (${resp["size_mb"]} MB)', AppColors.success);
      }
    } catch (e) {
      if (mounted) _showSnack('\u274c ${l10n.error}', e.toString(), AppColors.error);
    }
  }

  Future<void> _exportSeparate() async {
    if (_selectedFolder == null || _stems.isEmpty) return;
    final l10n = AppLocalizations.instance(context);
    try {
      final resp = await widget.api.stemExportSeparate(
        folderName: _selectedFolder!,
        volumes: _stemVolumes,
        masterVolume: _masterVolume,
        outputFormat: 'wav',
      );
      if (resp['status'] == 'ok' && mounted) {
        _showSnack('\u2705', '${(resp['files'] as List).length} ${l10n.files}', AppColors.success);
      }
    } catch (e) {
      if (mounted) _showSnack('\u274c ${l10n.error}', e.toString(), AppColors.error);
    }
  }

  Future<void> _extractMidi(_StemInfo stem) async {
    final l10n = AppLocalizations.instance(context);
    try {
      final resp = await widget.api.stemToMidi(stem.path);
      if (resp['status'] == 'ok' && mounted) {
        _showSnack('\ud83c\udfb9', '${resp["filename"]} (${resp["notes"]} notes)', AppColors.success);
      }
    } catch (e) {
      if (mounted) _showSnack('\u274c ${l10n.error}', e.toString(), AppColors.error);
    }
  }

  Future<void> _extractAllMidi() async {
    final melodicStems = _stems.where((s) => ['vocals', 'guitar', 'piano', 'bass'].contains(s.key)).toList();
    final l10n = AppLocalizations.instance(context);
    if (melodicStems.isEmpty) {
      if (mounted) _showSnack(l10n.extractMidi, l10n.noOutputsYet, AppColors.warning);
      return;
    }
    _showSnack('\ud83c\udfb9', '${l10n.extractMidi} (${melodicStems.length})', AppColors.warning);
    for (final stem in melodicStems) {
      await _extractMidi(stem);
    }
  }

  void _resetVolumes() {
    setState(() {
      _masterVolume = 1.0;
      for (final key in _stemVolumes.keys) {
        _stemVolumes[key] = 1.0;
      }
    });
  }

  void _showSnack(String title, String message, Color color) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('$title $message'),
        backgroundColor: color,
        behavior: SnackBarBehavior.floating,
      ),
    );
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
              Text(l10n.resultsAndStemMixer, style: AppTextStyles.heading(context)),
              const Spacer(),
              GhostButton(label: l10n.refresh, icon: Icons.refresh_rounded, onPressed: _loadOutputs),
            ],
          ),
          const SizedBox(height: 6),
          Text(l10n.resultsSubtitle, style: AppTextStyles.body(context)),
          const SizedBox(height: 24),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator(color: AppColors.accentPurple))
                : Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      SizedBox(width: 320, child: _buildOutputsList(l10n)),
                      const SizedBox(width: 24),
                      Expanded(child: _selectedFolder != null ? _buildStemMixer(l10n) : _buildEmptyState(l10n)),
                    ],
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildOutputsList(AppLocalizations l10n) {
    if (_outputs.isEmpty) {
      return GlassCard(
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.folder_off_rounded, size: 48, color: AppColors.textDim),
              const SizedBox(height: 12),
              Text(l10n.noOutputsYet, style: AppTextStyles.body(context)),
              Text(l10n.runSeparationToSee, style: AppTextStyles.caption(context)),
            ],
          ),
        ),
      );
    }
    return GlassCard(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(l10n.outputFolders, style: AppTextStyles.label(context)),
          const SizedBox(height: 8),
          Expanded(
            child: ListView.builder(
              itemCount: _outputs.length,
              itemBuilder: (ctx, i) {
                final folder = _outputs[i] as Map<String, dynamic>;
                final name = folder['name'] ?? '';
                final files = (folder['files'] as List?) ?? [];
                final selected = _selectedFolder == name;
                return Container(
                  margin: const EdgeInsets.only(bottom: 4),
                  child: Material(
                    color: Colors.transparent,
                    child: InkWell(
                      onTap: () => _selectFolder(name),
                      borderRadius: BorderRadius.circular(10),
                      child: Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: selected ? AppColors.accentPurple.withValues(alpha: 0.12) : Colors.transparent,
                          borderRadius: BorderRadius.circular(10),
                          border: selected ? Border.all(color: AppColors.accentPurple.withValues(alpha: 0.3)) : null,
                        ),
                        child: Row(
                          children: [
                            Icon(Icons.folder_rounded, size: 20, color: selected ? AppColors.accentPurple : AppColors.textDim),
                            const SizedBox(width: 10),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(name, style: AppTextStyles.body(context).copyWith(color: AppColors.textPrimary, fontSize: 13)),
                                  Text('${files.length} ${l10n.files.toLowerCase()}', style: AppTextStyles.caption(context)),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState(AppLocalizations l10n) {
    return GlassCard(
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.equalizer_rounded, size: 48, color: AppColors.textDim),
            const SizedBox(height: 12),
            Text(l10n.selectFolderToView, style: AppTextStyles.body(context)),
          ],
        ),
      ),
    );
  }

  Widget _buildStemMixer(AppLocalizations l10n) {
    return GlassCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SectionHeader(
            title: l10n.stemMixer,
            subtitle: '${_stems.length} ${l10n.stemsLoaded} $_selectedFolder',
            trailing: GhostButton(label: l10n.reset, icon: Icons.restart_alt_rounded, onPressed: _resetVolumes),
          ),
          Row(
            children: [
              Text(l10n.master, style: AppTextStyles.body(context).copyWith(fontWeight: FontWeight.w600)),
              const SizedBox(width: 12),
              Expanded(
                child: SliderTheme(
                  data: _sliderTheme(AppColors.accentPurple),
                  child: Slider(
                    value: _masterVolume,
                    min: 0,
                    max: 2,
                    onChanged: (v) => setState(() => _masterVolume = v),
                  ),
                ),
              ),
              SizedBox(width: 48, child: Text('${(_masterVolume * 100).toInt()}%', style: AppTextStyles.caption(context), textAlign: TextAlign.right)),
            ],
          ),
          const SizedBox(height: 12),
          Expanded(
            child: ListView.builder(
              itemCount: _stems.length,
              itemBuilder: (ctx, i) {
                final stem = _stems[i];
                final color = _stemColors[stem.colorIndex % _stemColors.length];
                final volume = _stemVolumes[stem.key] ?? 1.0;
                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Row(
                    children: [
                      SizedBox(width: 80, child: Text(stem.label, style: AppTextStyles.body(context).copyWith(color: color, fontWeight: FontWeight.w600, fontSize: 13))),
                      Expanded(
                        child: SliderTheme(
                          data: _sliderTheme(color),
                          child: Slider(
                            value: volume,
                            min: 0,
                            max: 2,
                            onChanged: (v) => setState(() => _stemVolumes[stem.key] = v),
                          ),
                        ),
                      ),
                      SizedBox(width: 48, child: Text('${(volume * 100).toInt()}%', style: AppTextStyles.caption(context), textAlign: TextAlign.right)),
                      if (['vocals', 'guitar', 'piano', 'bass'].contains(stem.key))
                        Padding(
                          padding: const EdgeInsets.only(left: 8),
                          child: Tooltip(
                            message: '${l10n.extractMidi} ${stem.label}',
                            child: Material(
                              color: Colors.transparent,
                              child: InkWell(
                                onTap: () => _extractMidi(stem),
                                borderRadius: BorderRadius.circular(6),
                                child: Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                  decoration: BoxDecoration(
                                    color: AppColors.info.withValues(alpha: 0.12),
                                    borderRadius: BorderRadius.circular(6),
                                    border: Border.all(color: AppColors.info.withValues(alpha: 0.3)),
                                  ),
                                  child: Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      Icon(Icons.piano_rounded, size: 12, color: AppColors.info),
                                      const SizedBox(width: 3),
                                      Text(l10n.extractMidi, style: TextStyle(fontSize: 10, color: AppColors.info, fontWeight: FontWeight.w600)),
                                    ],
                                  ),
                                ),
                              ),
                            ),
                          ),
                        ),
                    ],
                  ),
                );
              },
            ),
          ),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppColors.surfaceLight,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppColors.glassBorder),
            ),
            child: Column(
              children: [
                Row(
                  children: [
                    AccentButton(
                      label: _isPreviewing ? l10n.loading : (_isPlaying ? l10n.stop : l10n.play),
                      icon: _isPreviewing ? Icons.hourglass_top_rounded : (_isPlaying ? Icons.stop_rounded : Icons.play_arrow_rounded),
                      onPressed: _isPlaying ? _stopPreview : _previewMix,
                      compact: true,
                    ),
                    const SizedBox(width: 6),
                    GhostButton(label: l10n.exportMix, icon: Icons.save_alt_rounded, onPressed: _exportMix),
                    const SizedBox(width: 6),
                    GhostButton(label: l10n.exportAll, icon: Icons.folder_zip_rounded, onPressed: _exportSeparate),
                  ],
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    GhostButton(label: l10n.midiAll, icon: Icons.piano_rounded, onPressed: _extractAllMidi),
                    const SizedBox(width: 6),
                    GhostButton(label: l10n.reset, icon: Icons.restart_alt_rounded, onPressed: _resetVolumes),
                  ],
                ),
                if (_isPlaying) ...[
                  const SizedBox(height: 8),
                  VpProgressBar(value: (_previewPos / 15).clamp(0.0, 1.0)),
                  const SizedBox(height: 2),
                  Text('${_previewPos.toStringAsFixed(0)}s / 15s', style: AppTextStyles.caption(context)),
                ],
              ],
            ),
          ),
          const SizedBox(height: 12),
          Text(l10n.files.toUpperCase(), style: AppTextStyles.label(context)),
          const SizedBox(height: 8),
          ..._stems.map((s) => Container(
                margin: const EdgeInsets.only(bottom: 4),
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: AppColors.surfaceLight,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  children: [
                    Icon(Icons.audiotrack_rounded, size: 16, color: AppColors.textDim),
                    const SizedBox(width: 8),
                    Expanded(child: Text(s.filename, style: AppTextStyles.body(context).copyWith(fontSize: 12), overflow: TextOverflow.ellipsis)),
                    Text('${s.sizeMb.toStringAsFixed(1)} MB', style: AppTextStyles.caption(context)),
                    const SizedBox(width: 8),
                    Tooltip(
                      message: l10n.openFileLocation,
                      child: Material(
                        color: Colors.transparent,
                        child: InkWell(
                          onTap: () => _showSnack(l10n.open, s.path, AppColors.info),
                          borderRadius: BorderRadius.circular(6),
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                            decoration: BoxDecoration(
                              color: AppColors.accentPurple.withValues(alpha: 0.12),
                              borderRadius: BorderRadius.circular(6),
                              border: Border.all(color: AppColors.accentPurple.withValues(alpha: 0.3)),
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(Icons.folder_open_rounded, size: 12, color: AppColors.accentPurple),
                                const SizedBox(width: 3),
                                Text(l10n.open, style: TextStyle(fontSize: 10, color: AppColors.accentPurple, fontWeight: FontWeight.w600)),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              )),
        ],
      ),
    );
  }

  SliderThemeData _sliderTheme(Color color) => SliderThemeData(
        activeTrackColor: color,
        thumbColor: color,
        overlayColor: color.withValues(alpha: 0.15),
        inactiveTrackColor: AppColors.surfaceLight,
        trackHeight: 4,
        thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 7),
      );
}

class _StemInfo {
  final String key;
  final String label;
  final String filename;
  final String path;
  final double sizeMb;
  final int colorIndex;

  _StemInfo({
    required this.key,
    required this.label,
    required this.filename,
    required this.path,
    required this.sizeMb,
    required this.colorIndex,
  });
}

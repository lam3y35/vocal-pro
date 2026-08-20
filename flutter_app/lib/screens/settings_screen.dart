import 'dart:async';
import 'package:flutter/material.dart';
import '../theme.dart';
import '../widgets/cards.dart';
import '../widgets/changelog_dialog.dart';
import '../services/api_service.dart';

import '../utils/window_service.dart';
import '../utils/file_associations.dart';
import '../l10n/app_localizations.dart';
import '../l10n/locale_provider.dart';

/// Settings screen – all parameters matching Python DEFAULT_CONFIG + language picker.
class SettingsScreen extends StatefulWidget {
  final ApiService api;
  final LocaleProvider localeProvider;

  final WindowService windowService;
  const SettingsScreen({
    super.key,
    required this.api,
    required this.localeProvider,

    required this.windowService,
  });

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  Map<String, dynamic> _config = {};
  Map<String, dynamic> _defaults = {};
  bool _loading = true;
  final Map<String, TextEditingController> _textControllers = {};

  @override
  void initState() { super.initState(); _loadConfig(); }

  @override
  void dispose() {
    for (final c in _textControllers.values) { c.dispose(); }
    super.dispose();
  }

  Future<void> _loadConfig() async {
    if (!mounted) return;
    setState(() => _loading = true);
    try {
      final results = await Future.wait([
        widget.api.getConfig(),
        widget.api.getDefaults(),
      ]);
      final cfg = Map<String, dynamic>.from(results[0]['config'] ?? {});
      final defaults = Map<String, dynamic>.from(results[1]['defaults'] ?? {});
      if (!mounted) return;
      setState(() {
        _config = cfg;
        _defaults = defaults;
        _loading = false;
      });
    } catch (e) { if (mounted) setState(() => _loading = false); }
  }

  Future<void> _saveSetting(String key, dynamic value) async {
    setState(() => _config[key] = value);
    try { await widget.api.updateConfig(key, value); } catch (_) {}
  }

  /// Reset a single setting to its factory default value.
  Future<void> _resetToDefault(String key) async {
    final defaultVal = _defaults[key];
    if (defaultVal == null) return;
    await _saveSetting(key, defaultVal);
    if (!mounted) return;
    _showSnack(context, '↺ $key reset to default', AppColors.info);
  }

  /// Small reset button widget for individual settings.
  Widget _resetBtn(String key) {
    return GestureDetector(
      onTap: () => _resetToDefault(key),
      child: Tooltip(
        message: 'Reset to default',
        child: Container(
          padding: const EdgeInsets.all(4),
          decoration: BoxDecoration(
            color: AppColors.surfaceLight,
            borderRadius: BorderRadius.circular(6),
          ),
          child: Icon(Icons.refresh_rounded, size: 14, color: AppColors.textDim),
        ),
      ),
    );
  }

  static const _sliderSettings = [
    _SettingDef('segment', 'Segment Length (sec)', 2.0, 60.0, false, 'Higher = better quality, more VRAM'),
    _SettingDef('overlap', 'Overlap (sec)', 0.1, 8.0, false, 'More overlap = smoother crossfade'),
    _SettingDef('shifts', 'Model Passes (Shifts)', 1, 10, true, '1=Fast, 5+=Slow/Better quality'),
    _SettingDef('gate_threshold_db', 'Gate Threshold (dB)', -80.0, -10.0, false, 'Lower = more sensitive vocal detection'),
    _SettingDef('gate_floor_db', 'Gate Floor (dB)', -90.0, -20.0, false, 'Lower = quieter silence sections'),
    _SettingDef('denoise_strength', 'Denoise Strength', 0.0, 1.0, false, 'Balanced noise removal (0-1)'),
    _SettingDef('denoise_strength_low', 'Multi-band: Low (rumble)', 0.0, 1.0, false, 'Denoising strength for low frequency band'),
    _SettingDef('denoise_strength_mid', 'Multi-band: Mid (vocals)', 0.0, 1.0, false, 'Gentler to preserve voice quality'),
    _SettingDef('denoise_strength_high', 'Multi-band: High (hiss)', 0.0, 1.0, false, 'Denoising strength for high frequency band'),
    _SettingDef('sfx_separation_margin_db', 'SFX Separation Margin (dB)', 1.0, 30.0, false, 'Higher = more aggressive SFX separation'),
    _SettingDef('sfx_kernel_size', 'SFX HPSS Kernel Size', 5, 99, true, 'Smaller = better transient capture (odd)'),
    _SettingDef('sfx_margin_harmonic_db', 'SFX Harmonic Margin (dB)', 0.0, 30.0, false, 'Higher = pushes more content to SFX'),
    _SettingDef('sfx_margin_percussive_db', 'SFX Percussive Margin (dB)', 0.0, 30.0, false, 'Lower = keeps more content as SFX'),
    _SettingDef('min_vocal_duration', 'Min Vocal Duration (sec)', 0.01, 5.0, false, 'Minimum vocal segment to keep'),
    _SettingDef('large_file_threshold_minutes', 'Large File Threshold (min)', 1, 480, true, 'Files above this use chunked processing'),
    _SettingDef('max_threads', 'Max CPU Threads', 0, 128, true, '0 = auto-detect (use all cores)'),
    _SettingDef('cooldown_between_chunks_seconds', 'Chunk Cooldown (sec)', 0.0, 60.0, false, 'Pause between chunk processing'),
  ];

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.instance(context);
    return Padding(padding: const EdgeInsets.all(32), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(l10n.settings, style: AppTextStyles.heading(context)),
      const SizedBox(height: 6), Text(l10n.settingsSubtitle, style: AppTextStyles.body(context)),
      const SizedBox(height: 24),
      Expanded(child: _loading
        ? const Center(child: CircularProgressIndicator(color: AppColors.accentPurple))
        : SingleChildScrollView(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            _buildLanguageCard(l10n), const SizedBox(height: 16),
            _buildGeneralCard(l10n), const SizedBox(height: 16),
            _buildWindowCard(l10n), const SizedBox(height: 16),
            _buildSliderCard(), const SizedBox(height: 16),
          ]))),
    ]));
  }

  // ── Window / Behavior Settings ─────────────────────────────────

  Widget _buildWindowCard(AppLocalizations l10n) {
    final winSvc = widget.windowService;
    return ListenableBuilder(
      listenable: winSvc,
      builder: (context, _) => GlassCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        SectionHeader(title: 'WINDOW', subtitle: 'Always-on-top, tray, and file associations'),
        _buildToggleRow(
          'Always on Top',
          'Pin the app window above all others',
          winSvc.alwaysOnTop,
          (v) => winSvc.setAlwaysOnTop(v),
          configKey: null, // window settings are local, not from backend config
        ),
        _buildToggleRow(
          'Minimize to Tray',
          'Minimize to system tray instead of closing',
          winSvc.minimizeToTray,
          (v) => winSvc.setMinimizeToTray(v),
        ),
        const SizedBox(height: 8),
        Row(children: [
          GhostButton(
            label: 'File Associations',
            icon: Icons.insert_drive_file_rounded,
            onPressed: () {
              registerFileAssociations();
              _showSnack(context, '✅ File associations registered', AppColors.success);
            },
          ),
          const SizedBox(width: 8),
          GhostButton(
            label: "What's New",
            icon: Icons.auto_awesome_rounded,
            onPressed: () => ChangelogDialog.show(context),
          ),
        ]),
      ])),
    );
  }

  // ── Language Picker ────────────────────────────────────────────

  Widget _buildLanguageCard(AppLocalizations l10n) {
    final currentLang = widget.localeProvider.locale.languageCode;
    final langs = AppLocalizations.displayedLocales;
    return GlassCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      SectionHeader(title: l10n.language, subtitle: l10n.languageDesc),
      const SizedBox(height: 8),
      Wrap(spacing: 6, runSpacing: 6, children: langs.map((locale) {
        final code = locale.languageCode;
        final name = AppLocalizations.languageNames[code] ?? code;
        final flag = _flagFor(code);
        final selected = code == currentLang;
        return GestureDetector(onTap: () => widget.localeProvider.setLocale(Locale(code)),
          child: AnimatedContainer(duration: const Duration(milliseconds: 200),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: selected ? AppColors.accentPurple.withValues(alpha: 0.2) : AppColors.surfaceLight,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: selected ? AppColors.accentPurple : AppColors.glassBorder)),
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              Text('$flag ', style: const TextStyle(fontSize: 16)),
              Text(name, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600,
                color: selected ? AppColors.accentPurple : AppColors.textPrimary)),
            ])));
      }).toList()),
    ]));
  }

  String _flagFor(String code) {
    const flags = {
      'en': '🇺🇸', 'es': '🇪🇸', 'fr': '🇫🇷', 'de': '🇩🇪', 'it': '🇮🇹',
      'pt': '🇧🇷', 'ru': '🇷🇺', 'ja': '🇯🇵', 'zh': '🇨🇳', 'ko': '🇰🇷',
      'ar': '🇸🇦', 'hi': '🇮🇳', 'tr': '🇹🇷', 'nl': '🇳🇱', 'pl': '🇵🇱', 'sv': '🇸🇪',
    };
    return flags[code] ?? '🌐';
  }

  // ── General Settings (toggles) ─────────────────────────────────

  Widget _buildGeneralCard(AppLocalizations l10n) {
    return GlassCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      SectionHeader(title: l10n.general, subtitle: l10n.processingBehavior),
      _buildToggleRow(l10n.safeMode, l10n.safeModeDesc, _config['safe_mode'] ?? false, (v) => _saveSetting('safe_mode', v), configKey: 'safe_mode'),
      _buildToggleRow(l10n.autoPreview, l10n.autoPreviewDesc, _config['auto_preview'] ?? false, (v) => _saveSetting('auto_preview', v), configKey: 'auto_preview'),
      _buildToggleRow('Output All Stems', 'Save all separated stems individually', _config['output_all_stems'] ?? true, (v) => _saveSetting('output_all_stems', v), configKey: 'output_all_stems'),
      _buildToggleRow('Output Video', 'Mux clean audio back to video when input is video', _config['output_video'] ?? true, (v) => _saveSetting('output_video', v), configKey: 'output_video'),
      _buildToggleRow('Faststart', 'Optimize MP4 for streaming (movflags +faststart)', _config['ffmpeg_faststart'] ?? true, (v) => _saveSetting('ffmpeg_faststart', v), configKey: 'ffmpeg_faststart'),
      const SizedBox(height: 12),
      Text(l10n.outputFormat, style: AppTextStyles.body(context)),
      const SizedBox(height: 4),
      Row(children: [
        ...['wav', 'mp3', 'flac'].map((fmt) {
          final selected = (_config['output_format'] ?? 'wav') == fmt;
          return Padding(padding: const EdgeInsets.only(right: 8), child: GestureDetector(onTap: () => _saveSetting('output_format', fmt),
            child: Container(padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
              decoration: BoxDecoration(color: selected ? AppColors.accentPurple.withValues(alpha: 0.2) : AppColors.surfaceLight,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: selected ? AppColors.accentPurple : AppColors.glassBorder)),
              child: Text(fmt.toUpperCase(), style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600,
                color: selected ? AppColors.accentPurple : AppColors.textDim)))));
        }),
        const Spacer(),
        _resetBtn('output_format'),
      ]),
      const SizedBox(height: 12),
      _buildTextFieldSetting(l10n.audioBitrate, 'audio_bitrate', '320k'),
      const SizedBox(height: 8),
      _buildTextFieldSetting('Device', 'device', 'auto'),
      _buildTextFieldSetting('Chunk Duration (min)', 'chunk_duration_minutes', '12'),
      _buildTextFieldSetting('Overlap Seconds', 'overlap_seconds', '5'),
    ]));
  }

  // ── Advanced Tuning Sliders ───────────────────────────────────

  Widget _buildSliderCard() {
    return GlassCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const SectionHeader(title: 'ADVANCED TUNING'),
      ..._sliderSettings.map((s) => _buildSlider(s)),
    ]));
  }

  // ── Widget builders ──────────────────────────────────────────

  Widget _buildToggleRow(String title, String subtitle, bool value, ValueChanged<bool> onChanged, {String? configKey}) {
    return Padding(padding: const EdgeInsets.symmetric(vertical: 6), child: Row(children: [
      Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(title, style: AppTextStyles.body(context)), Text(subtitle, style: AppTextStyles.caption(context)),
      ])),
      if (configKey != null) Padding(padding: const EdgeInsets.only(right: 8), child: _resetBtn(configKey)),
      Switch(value: value, onChanged: onChanged, activeTrackColor: AppColors.accentPurple, inactiveTrackColor: AppColors.surfaceLight),
    ]));
  }

  Widget _buildTextFieldSetting(String label, String configKey, String defaultValue) {
    final controller = _textControllers.putIfAbsent(configKey, () => TextEditingController(text: _config[configKey]?.toString() ?? defaultValue));
    if (controller.text != (_config[configKey]?.toString() ?? defaultValue)) {
      controller.text = _config[configKey]?.toString() ?? defaultValue;
    }
    return Padding(padding: const EdgeInsets.only(bottom: 8), child: Row(children: [
      SizedBox(width: 150, child: Text(label, style: AppTextStyles.body(context))),
      Expanded(child: Container(padding: const EdgeInsets.symmetric(horizontal: 12),
        decoration: BoxDecoration(color: AppColors.surfaceLight, borderRadius: BorderRadius.circular(8), border: Border.all(color: AppColors.glassBorder)),
        child: TextField(controller: controller, style: AppTextStyles.mono(context),
          decoration: const InputDecoration(border: InputBorder.none), onChanged: (v) => _saveSetting(configKey, v)))),
      if (_defaults.containsKey(configKey)) Padding(padding: const EdgeInsets.only(left: 8), child: _resetBtn(configKey)),
    ]));
  }

  Widget _buildSlider(_SettingDef def) {
    final currentVal = (_config[def.key] as num?)?.toDouble() ?? def.min;
    return Padding(padding: const EdgeInsets.only(bottom: 16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(def.label, style: AppTextStyles.body(context)),
          if (def.description != null) Text(def.description!, style: AppTextStyles.caption(context)),
        ])),
        Text(def.isInt ? currentVal.toInt().toString() : currentVal.toStringAsFixed(def.key.contains('db') ? 0 : 2),
          style: AppTextStyles.body(context).copyWith(color: AppColors.accentPurple, fontWeight: FontWeight.w600)),
        const SizedBox(width: 8),
        _resetBtn(def.key),
      ]),
      SliderTheme(data: SliderThemeData(activeTrackColor: AppColors.accentPurple, thumbColor: AppColors.accentPurple,
        overlayColor: AppColors.accentPurple.withValues(alpha: 0.15), inactiveTrackColor: AppColors.surfaceLight,
        trackHeight: 4, thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 7)),
        child: Slider(value: currentVal.clamp(def.min, def.max), min: def.min, max: def.max,
          divisions: def.isInt ? (def.max - def.min).toInt() : null,
          onChanged: (v) { final val = def.isInt ? v.roundToDouble() : v; setState(() => _config[def.key] = val); },
          onChangeEnd: (v) { final val = def.isInt ? v.round() : v; _saveSetting(def.key, val); })),
    ]));
  }

  void _showSnack(BuildContext context, String msg, Color color) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(msg), backgroundColor: color, behavior: SnackBarBehavior.floating));
  }


}

class _SettingDef {
  final String key; final String label; final double min; final double max; final bool isInt; final String? description;
  const _SettingDef(this.key, this.label, this.min, this.max, this.isInt, [this.description]);
}

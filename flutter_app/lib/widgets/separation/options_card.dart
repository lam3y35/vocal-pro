import 'package:flutter/material.dart';
import '../../controllers/separation_controller.dart';
import '../../l10n/app_localizations.dart';
import '../../theme.dart';
import '../cards.dart';

/// Options card — format chips, video mode chips, processing checkboxes, output checkboxes.
class OptionsCard extends StatelessWidget {
  final SeparationController ctrl;
  const OptionsCard({super.key, required this.ctrl});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.instance(context);
    return ListenableBuilder(
      listenable: ctrl,
      builder: (context, _) {
        final sm = ctrl.songMode;
        return GlassCard(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            SectionHeader(title: l10n.options),
            // Format + Video mode row
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(children: [
                Text('${l10n.format} ', style: AppTextStyles.body(context)),
                const SizedBox(width: 12),
                _formatChip(context, 'wav'), const SizedBox(width: 6),
                _formatChip(context, 'mp3'), const SizedBox(width: 6),
                _formatChip(context, 'flac'),
                const SizedBox(width: 24),
                Text('${l10n.video} ', style: AppTextStyles.body(context)),
                const SizedBox(width: 8),
                _videoModeChip(context, 'both', sm),
                const SizedBox(width: 4),
                _videoModeChip(context, 'video_only', sm),
                const SizedBox(width: 4),
                _videoModeChip(context, 'audio_only', sm),
              ]),
            ),
            const SizedBox(height: 16),
            Text(l10n.processing, style: AppTextStyles.label(context)),
            const SizedBox(height: 8),
            _checkboxRow(context, l10n.reduceNoise, 'reduceNoise', sm || ctrl.enableDenoise, (v) => ctrl.enableDenoise = v, locked: sm),
            _checkboxRow(context, l10n.muteWithoutVocals, 'muteWithoutVocals', sm || ctrl.enableGate, (v) => ctrl.enableGate = v, locked: sm),
            _checkboxRow(context, l10n.multibandNoise, 'multibandNoise', sm || ctrl.enableMultiband, (v) => ctrl.enableMultiband = v, locked: sm),
            _checkboxRow(context, l10n.autoDetectNoise, 'autoDetectNoise', sm || ctrl.enableProfile, (v) => ctrl.enableProfile = v, locked: sm),
            _checkboxRow(context, l10n.dynamicGate, 'dynamicGate', sm || ctrl.adaptiveGate, (v) => ctrl.adaptiveGate = v, locked: sm),
            _checkboxRow(context, l10n.trimSilence, 'trimSilence', sm ? true : ctrl.trimSilence, (v) => ctrl.trimSilence = v, locked: sm),
            _checkboxRow(context, l10n.ensembleMode, 'ensembleMode', ctrl.ensembleMode, (v) => ctrl.ensembleMode = v),
            const SizedBox(height: 12),
            Text(l10n.output, style: AppTextStyles.label(context)),
            const SizedBox(height: 8),
            _checkboxRow(context, l10n.mixWithSfx, 'mixWithSfx', sm ? false : ctrl.includeSfx, (v) => ctrl.includeSfx = v, locked: sm),
            _checkboxRow(context, l10n.saveBackground, 'saveBackground', sm ? false : ctrl.saveBg, (v) => ctrl.saveBg = v, locked: sm),
            _checkboxRow(context, l10n.karaokeMode, 'karaokeMode', sm ? false : ctrl.karaokeMode, (v) => ctrl.karaokeMode = v, locked: sm),
            _checkboxRow(context, l10n.generateComparisonSamples, 'generateComparisonSamples', ctrl.genSamples, (v) => ctrl.genSamples = v),
          ]),
        );
      },
    );
  }

  static const _formatTooltips = {
    'wav': 'Uncompressed audio, highest quality, large file size',
    'mp3': 'Compressed audio, smaller file size, slight quality loss',
    'flac': 'Lossless compressed audio, high quality, smaller than WAV',
  };

  Widget _formatChip(BuildContext context, String fmt) {
    final selected = ctrl.outputFormat == fmt;
    return Tooltip(
      message: _formatTooltips[fmt]!,
      waitDuration: const Duration(milliseconds: 300),
      child: GestureDetector(
        onTap: () => ctrl.outputFormat = fmt,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
          decoration: BoxDecoration(
            color: selected ? AppColors.accentPurple.withValues(alpha: 0.2) : AppColors.surfaceLight,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: selected ? AppColors.accentPurple : AppColors.glassBorder),
          ),
          child: Text(
            fmt.toUpperCase(),
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: selected ? AppColors.accentPurple : AppColors.textDim,
            ),
          ),
        ),
      ),
    );
  }

  static const _videoTooltips = {
    'both': 'Keep video with clean audio and export separate audio file',
    'video_only': 'Replace video audio with clean version, delete separate audio file',
    'audio_only': 'Only export audio files, no video output',
  };

  Widget _videoModeChip(BuildContext context, String mode, bool locked) {
    final l10n = AppLocalizations.instance(context);
    final labels = {'both': l10n.videoPlusAudio, 'video_only': l10n.videoOnly, 'audio_only': l10n.audioOnly};
    final forcedAudioOnly = locked && mode == 'audio_only';
    final selected = forcedAudioOnly || ctrl.videoOutputMode == mode;
    return Tooltip(
      message: _videoTooltips[mode]!,
      waitDuration: const Duration(milliseconds: 300),
      child: GestureDetector(
        onTap: locked ? null : () => ctrl.videoOutputMode = mode,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: selected ? AppColors.accentPurple.withValues(alpha: 0.2) : AppColors.surfaceLight,
            borderRadius: BorderRadius.circular(6),
            border: Border.all(color: selected ? AppColors.accentPurple : AppColors.glassBorder),
          ),
          child: Text(
            labels[mode]!,
            style: TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w600,
              color: selected ? AppColors.accentPurple : AppColors.textDim,
            ),
          ),
        ),
      ),
    );
  }

  /// Tooltip explanations keyed by localization key (not localized value)
  /// so they work in any language.
  static const _optionExplanations = {
    'reduceNoise': 'Reduce background music bleed in the extracted vocals',
    'muteWithoutVocals': 'Silence instrumental-only sections between vocal passages',
    'multibandNoise': 'Denoise low/mid/high frequency bands separately for precision',
    'autoDetectNoise': 'Auto-sample noise profile from silent sections for targeted denoising',
    'dynamicGate': 'Auto-adjust gate floor based on actual noise level for optimal silence',
    'trimSilence': 'Remove leading and trailing silence from output files',
    'ensembleMode': 'Run multiple AI models and average results for better quality',
    'mixWithSfx': 'Include sound effects and ambience mixed into the vocals (or instrumental in Song mode)',
    'saveBackground': 'Save the background music track as a separate file',
    'karaokeMode': 'Remove vocals entirely, output instrumental-only audio',
    'generateComparisonSamples': 'Create short comparison clips of original vs processed audio',
  };

  Widget _checkboxRow(BuildContext context, String label, String tooltipKey, bool value,
      ValueChanged<bool> onChanged, {bool locked = false}) {
    final dimmed = locked ? 0.4 : 1.0;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(children: [
        // Tooltip only wraps the checkbox square, not the text label or padding,
        // so it only activates on direct hover — not on proximity.
        Tooltip(
          message: _optionExplanations[tooltipKey] ?? label,
          waitDuration: const Duration(milliseconds: 500),
          child: GestureDetector(
            onTap: locked ? null : () => onChanged(!value),
            child: Container(
              width: 20,
              height: 20,
              decoration: BoxDecoration(
                color: value ? AppColors.accentPurple : Colors.transparent,
                borderRadius: BorderRadius.circular(4),
                border: Border.all(color: value ? AppColors.accentPurple : AppColors.glassBorder),
              ),
              child: value ? const Icon(Icons.check_rounded, size: 14, color: Colors.white) : null,
            ),
          ),
        ),
        const SizedBox(width: 10),
        Text(
          label,
          style: AppTextStyles.body(context).copyWith(
            fontSize: 13,
            color: AppColors.textSecondary.withValues(alpha: dimmed),
          ),
        ),
      ]),
    );
  }
}

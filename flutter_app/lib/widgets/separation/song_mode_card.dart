import 'package:flutter/material.dart';
import '../../controllers/separation_controller.dart';
import '../../l10n/app_localizations.dart';
import '../../theme.dart';
import '../cards.dart';

/// Song Mode card — toggle on/off with mode indicators when active.
class SongModeCard extends StatelessWidget {
  final SeparationController ctrl;
  const SongModeCard({super.key, required this.ctrl});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.instance(context);
    return ListenableBuilder(
      listenable: ctrl,
      builder: (context, _) {
        final active = ctrl.songMode;
        return GlassCard(
          highlighted: active,
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Tooltip(
              message: 'One-tap preset: trim silence, enable denoise/gate, audio-only output \u2014 ideal for songs',
              waitDuration: const Duration(milliseconds: 300),
              child: InkWell(
                onTap: () => ctrl.songMode = !active,
                borderRadius: BorderRadius.circular(8),
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(children: [
                  Container(
                    width: 48,
                    height: 48,
                    decoration: BoxDecoration(
                      color: active
                          ? AppColors.accentPurple.withValues(alpha: 0.15)
                          : AppColors.surfaceLight,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Center(
                      child: Text('\uD83C\uDFA4', style: TextStyle(fontSize: active ? 26 : 22)),
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Row(children: [
                        Text(
                          l10n.songMode,
                          style: AppTextStyles.subheading(context).copyWith(
                            color: active ? AppColors.accentPurple : AppColors.textPrimary,
                          ),
                        ),
                        const SizedBox(width: 8),
                        if (active)
                          Icon(Icons.check_circle_rounded, size: 18, color: AppColors.accentPurple),
                      ]),
                      const SizedBox(height: 2),
                      Text(
                        active ? l10n.songModeActiveDesc : l10n.songModeInactiveDesc,
                        style: AppTextStyles.caption(context),
                      ),
                    ]),
                  ),
                  const SizedBox(width: 12),
                  Switch(
                    value: active,
                    onChanged: (v) => ctrl.songMode = v,
                    activeTrackColor: AppColors.accentPurple.withValues(alpha: 0.3),
                  ),
                ]),
              ),
            ),
            ),
            if (active) ...[
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppColors.accentPurple.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: AppColors.accentPurple.withValues(alpha: 0.2)),
                ),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  _modeIndicator(l10n.songModeAudioOnly, Icons.volume_up_rounded, AppColors.info),
                  const SizedBox(height: 6),
                  _modeIndicator(l10n.songModeVocalsOnly, Icons.mic_rounded, AppColors.success),
                  const SizedBox(height: 6),
                  _modeIndicator(l10n.songModeTrimSilence, Icons.content_cut_rounded, AppColors.warning),
                  const SizedBox(height: 6),
                  _modeIndicator(l10n.songModeDenoiseGate, Icons.auto_fix_high_rounded, AppColors.accentPurple),
                ]),
              ),
            ],
          ]),
        );
      },
    );
  }

  Widget _modeIndicator(String text, IconData icon, Color color) {
    return Row(children: [
      Icon(icon, size: 14, color: color),
      const SizedBox(width: 8),
      Text(text, style: TextStyle(fontSize: 12, color: AppColors.textSecondary)),
    ]);
  }
}

import 'package:flutter/material.dart';
import '../../controllers/separation_controller.dart';
import '../../l10n/app_localizations.dart';
import '../../theme.dart';
import '../cards.dart';
import '../waveform_view.dart';

/// Waveform preview card — shows waveform, play/pause/seek controls.
/// Uses real audio playback via [SeparationController]'s audioplayers integration.
class WaveformCard extends StatelessWidget {
  final SeparationController ctrl;
  const WaveformCard({super.key, required this.ctrl});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.instance(context);
    return ListenableBuilder(
      listenable: ctrl,
      builder: (context, _) => GlassCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          SectionHeader(
            title: l10n.preview,
            trailing: ctrl.waveformData != null
                ? Row(mainAxisSize: MainAxisSize.min, children: [
                    _formatTime(ctrl.currentPosSec),
                    Text(' / ', style: AppTextStyles.caption(context)),
                    _formatTime(ctrl.durationSec),
                    const SizedBox(width: 8),
                    GhostButton(
                      label: ctrl.isPlaying ? l10n.pause : l10n.play,
                      icon: ctrl.isPlaying ? Icons.pause_rounded : Icons.play_arrow_rounded,
                      onPressed: ctrl.waveformData != null ? ctrl.togglePlayback : null,
                      compact: true,
                    ),
                    if (ctrl.isPlaying) ...[
                      const SizedBox(width: 4),
                      GhostButton(
                        label: l10n.stop,
                        icon: Icons.stop_rounded,
                        onPressed: ctrl.stopPlayback,
                        compact: true,
                      ),
                    ],
                  ])
                : null,
          ),
          WaveformView(
            waveformData: ctrl.waveformData,
            durationSec: ctrl.durationSec,
            currentPositionSec: ctrl.currentPosSec,
            isPlaying: ctrl.isPlaying,
            onPlayPause: ctrl.togglePlayback,
            onStop: ctrl.stopPlayback,
            onSeek: ctrl.seekTo,
          ),
          if (ctrl.waveformData == null)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(l10n.addFileForWaveform, style: AppTextStyles.caption(context)),
            ),
        ]),
      ),
    );
  }

  Widget _formatTime(double seconds) {
    final mins = (seconds ~/ 60).toInt();
    final secs = (seconds % 60).toInt();
    return Text(
      '${mins.toString().padLeft(2, '0')}:${secs.toString().padLeft(2, '0')}',
      style: TextStyle(
        fontFamily: 'monospace',
        color: AppColors.textPrimary,
        fontWeight: FontWeight.w600,
        fontSize: 13,
      ),
    );
  }
}

import 'dart:math' as math;

import 'package:flutter/material.dart';
import '../theme.dart';

/// Waveform visualization widget with play/pause, scrub, and time display.
/// Renders stylized amplitude bars that animate during playback.
class WaveformPreview extends StatefulWidget {
  /// Duration of the audio in seconds.
  final double duration;

  /// List of amplitude values (0.0–1.0) to render as bars.
  /// If empty, generates randomized placeholder bars.
  final List<double>? amplitudes;

  /// Currently playing position as fraction (0.0–1.0).
  final double position;

  /// Whether playback is active.
  final bool isPlaying;

  /// Called when user taps or drags to seek.
  final ValueChanged<double>? onSeek;

  /// Called when play/pause button is tapped.
  final VoidCallback? onPlayPause;

  const WaveformPreview({
    super.key,
    this.duration = 0,
    this.amplitudes,
    this.position = 0,
    this.isPlaying = false,
    this.onSeek,
    this.onPlayPause,
  });

  @override
  State<WaveformPreview> createState() => _WaveformPreviewState();
}

class _WaveformPreviewState extends State<WaveformPreview>
    with SingleTickerProviderStateMixin {
  late AnimationController _animController;
  List<double> _bars = [];
  bool _isHovering = false;

  @override
  void initState() {
    super.initState();
    _animController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 300),
    );
    _generateBars();
  }

  @override
  void didUpdateWidget(WaveformPreview oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.amplitudes != widget.amplitudes) {
      _generateBars();
    }
    if (widget.isPlaying) {
      _animController.repeat(
        period: const Duration(milliseconds: 1200),
      );
    } else {
      _animController.stop();
      _animController.reset();
    }
  }

  @override
  void dispose() {
    _animController.dispose();
    super.dispose();
  }

  void _generateBars() {
    final rng = math.Random(42); // fixed seed for consistent placeholder
    if (widget.amplitudes != null && widget.amplitudes!.isNotEmpty) {
      _bars = widget.amplitudes!;
    } else {
      _bars = List.generate(80, (_) => 0.2 + rng.nextDouble() * 0.6);
    }
  }

  String _formatTime(double seconds) {
    final m = (seconds ~/ 60).toString().padLeft(2, '0');
    final s = (seconds % 60).toStringAsFixed(0).padLeft(2, '0');
    return '$m:$s';
  }

  @override
  Widget build(BuildContext context) {
    final currentTime = widget.position * widget.duration;
    final remaining = widget.duration - currentTime;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        // Time display
        Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: Row(
            children: [
              Text(
                _formatTime(currentTime),
                style: AppTextStyles.mono(context).copyWith(
                  color: AppColors.textPrimary,
                  fontSize: 11,
                ),
              ),
              const Spacer(),
              Text(
                '-${_formatTime(remaining)}',
                style: AppTextStyles.mono(context).copyWith(fontSize: 11),
              ),
            ],
          ),
        ),

        // Waveform canvas
        LayoutBuilder(
          builder: (context, constraints) {
            return GestureDetector(
              onTapDown: (details) => _seek(details.localPosition.dx, constraints.maxWidth),
              onHorizontalDragUpdate: (details) => _seek(
                details.localPosition.dx.clamp(0, constraints.maxWidth),
                constraints.maxWidth,
              ),
              child: MouseRegion(
                onEnter: (_) => setState(() => _isHovering = true),
                onExit: (_) => setState(() => _isHovering = false),
                cursor: _isHovering
                    ? SystemMouseCursors.click
                    : SystemMouseCursors.basic,
                child: AnimatedBuilder(
                  animation: _animController,
                  builder: (context, _) {
                    return CustomPaint(
                      size: Size(constraints.maxWidth, 80),
                      painter: _WaveformPainter(
                        bars: _bars,
                        position: widget.position,
                        isPlaying: widget.isPlaying,
                        animValue: _animController.value,
                        isHovering: _isHovering,
                      ),
                    );
                  },
                ),
              ),
            );
          },
        ),

        const SizedBox(height: 8),

        // Play controls
        Row(
          children: [
            // Play/Pause button
            Material(
              color: Colors.transparent,
              child: InkWell(
                onTap: widget.onPlayPause,
                borderRadius: BorderRadius.circular(20),
                child: Container(
                  width: 36,
                  height: 36,
                  decoration: BoxDecoration(
                    gradient: AppColors.accentGradient,
                    borderRadius: BorderRadius.circular(20),
                    boxShadow: [
                      BoxShadow(
                        color: AppColors.accentPurple.withValues(alpha: 0.3),
                        blurRadius: 8,
                      ),
                    ],
                  ),
                  child: Icon(
                    widget.isPlaying
                        ? Icons.pause_rounded
                        : Icons.play_arrow_rounded,
                    color: Colors.white,
                    size: 18,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 12),

            // Progress bar
            Expanded(
              child: SliderTheme(
                data: SliderThemeData(
                  activeTrackColor: AppColors.accentPurple,
                  thumbColor: AppColors.accentPurple,
                  overlayColor: AppColors.accentPurple.withValues(alpha: 0.15),
                  inactiveTrackColor: AppColors.surfaceLight,
                  trackHeight: 3,
                  thumbShape: const RoundSliderThumbShape(
                    enabledThumbRadius: 5,
                  ),
                ),
                child: Slider(
                  value: widget.position.clamp(0.0, 1.0),
                  onChanged: (v) => widget.onSeek?.call(v),
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }

  void _seek(double dx, double totalWidth) {
    final pos = (dx / totalWidth).clamp(0.0, 1.0);
    widget.onSeek?.call(pos);
  }
}

/// Custom painter for waveform bars with accent gradient, glow, and
/// playback position indicator.
class _WaveformPainter extends CustomPainter {
  final List<double> bars;
  final double position;
  final bool isPlaying;
  final double animValue;
  final bool isHovering;

  _WaveformPainter({
    required this.bars,
    required this.position,
    required this.isPlaying,
    required this.animValue,
    required this.isHovering,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final barCount = bars.length;
    final gap = 2.0;
    final barW = (size.width - (barCount - 1) * gap) / barCount;
    final centerY = size.height / 2;
    final maxHeight = size.height * 0.9;

    // Draw background
    final bgPaint = Paint()
      ..color = AppColors.surfaceLight.withValues(alpha: 0.5);
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(0, 0, size.width, size.height),
        const Radius.circular(8),
      ),
      bgPaint,
    );

    final playedCount = (position * barCount).floor();

    for (int i = 0; i < barCount; i++) {
      final isPlayed = i <= playedCount;

      // Animate amplitude subtly when playing
      double amp = bars[i];
      if (isPlaying) {
        final wave = math.sin(animValue * 2 * math.pi - i * 0.3);
        amp += wave * 0.08; // subtle movement
        amp = amp.clamp(0.05, 0.95);
      }

      final h = maxHeight * amp;
      final x = i * (barW + gap);

      // Color: played bars get accent, unplayed get dim
      final Color barColor;
      if (isPlayed) {
        barColor = Color.lerp(
          AppColors.accentPurple,
          AppColors.accentPink,
          i / barCount,
        )!;
      } else {
        barColor = AppColors.textDim.withValues(alpha: 0.2);
      }

      // Hover glow on current position
      if (isHovering && i == playedCount.clamp(0, barCount - 1)) {
        final glowPaint = Paint()
          ..color = AppColors.accentPurple.withValues(alpha: 0.15)
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 6);
        canvas.drawCircle(
          Offset(x + barW / 2, centerY),
          barW * 2,
          glowPaint,
        );
      }

      final paint = Paint()..color = barColor;
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromCenter(
            center: Offset(x + barW / 2, centerY),
            width: barW,
            height: h,
          ),
          Radius.circular(barW / 2),
        ),
        paint,
      );
    }

    // Playhead line
    final playheadX = position * size.width;
    final playheadPaint = Paint()
      ..color = Colors.white.withValues(alpha: 0.6)
      ..strokeWidth = 1.5;
    canvas.drawLine(
      Offset(playheadX, 4),
      Offset(playheadX, size.height - 4),
      playheadPaint,
    );
  }

  @override
  bool shouldRepaint(_WaveformPainter oldDelegate) =>
      oldDelegate.position != position ||
      oldDelegate.animValue != animValue ||
      oldDelegate.isPlaying != isPlaying ||
      oldDelegate.isHovering != isHovering ||
      oldDelegate.bars != bars;
}

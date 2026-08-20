import 'dart:math' as math;

import 'package:flutter/material.dart';
import '../theme.dart';

/// Waveform display widget with playback cursor and time labels.
class WaveformView extends StatefulWidget {
  final List<double>? waveformData;
  final double durationSec;
  final double currentPositionSec;
  final bool isPlaying;
  final VoidCallback? onPlayPause;
  final VoidCallback? onStop;
  final ValueChanged<double>? onSeek;

  const WaveformView({
    super.key,
    this.waveformData,
    this.durationSec = 0,
    this.currentPositionSec = 0,
    this.isPlaying = false,
    this.onPlayPause,
    this.onStop,
    this.onSeek,
  });

  @override
  State<WaveformView> createState() => _WaveformViewState();
}

class _WaveformViewState extends State<WaveformView> {
  @override
  Widget build(BuildContext context) {
    final hasWaveform = widget.waveformData != null && widget.waveformData!.isNotEmpty;

    return Container(
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.glassBorder),
      ),
      padding: const EdgeInsets.all(8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Waveform canvas
          SizedBox(
            height: 80,
            child: hasWaveform ? _buildWaveform() : _buildEmptyWaveform(),
          ),
          const SizedBox(height: 6),
          // Controls row
          Row(
            children: [
              // Play/Pause button
              GestureDetector(
                onTap: widget.onPlayPause,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: widget.isPlaying
                        ? AppColors.warning.withValues(alpha: 0.15)
                        : AppColors.accentPurple.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(
                      color: widget.isPlaying
                          ? AppColors.warning.withValues(alpha: 0.3)
                          : AppColors.accentPurple.withValues(alpha: 0.3),
                    ),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        widget.isPlaying ? Icons.pause_rounded : Icons.play_arrow_rounded,
                        size: 16,
                        color: widget.isPlaying ? AppColors.warning : AppColors.accentPurple,
                      ),
                      const SizedBox(width: 4),
                      Text(
                        widget.isPlaying ? 'Pause' : 'Play',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: widget.isPlaying ? AppColors.warning : AppColors.accentPurple,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(width: 6),
              // Stop button
              GestureDetector(
                onTap: widget.onStop,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
                  decoration: BoxDecoration(
                    color: AppColors.error.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: AppColors.error.withValues(alpha: 0.3)),
                  ),
                  child: Icon(Icons.stop_rounded, size: 16, color: AppColors.error),
                ),
              ),
              const SizedBox(width: 12),
              // Time label
              Text(
                '${_formatTime(widget.currentPositionSec)} / ${_formatTime(widget.durationSec)}',
                style: AppTextStyles.mono(context).copyWith(fontSize: 11),
              ),
              if (hasWaveform) ...[
                const Spacer(),
                Text(
                  '${widget.waveformData!.length} points',
                  style: AppTextStyles.caption(context),
                ),
              ],
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyWaveform() {
    return Center(
      child: Text(
        'No audio loaded',
        style: AppTextStyles.caption(context),
      ),
    );
  }

  Widget _buildWaveform() {
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.maxWidth;
        final height = constraints.maxHeight;
        final mid = height / 2;
        final data = widget.waveformData!;
        final numPoints = math.min(data.length, width.toInt());
        final step = data.length / numPoints;
        final peak = data.map((v) => v.abs()).fold(0.0, (a, b) => a > b ? a : b).clamp(0.001, double.infinity);
        final scale = (height - 8) / 2 / peak;

        // Build path
        final path = Path();
        final xScale = width / math.max(1, numPoints - 1);

        for (int i = 0; i < numPoints; i++) {
          final idx = (i * step).toInt().clamp(0, data.length - 1);
          final x = i * xScale;
          final y = mid - data[idx] * scale;
          if (i == 0) {
            path.moveTo(x, y);
          } else {
            path.lineTo(x, y);
          }
        }

        // Cursor position
        double? cursorX;
        if (widget.durationSec > 0 && widget.currentPositionSec > 0) {
          cursorX = (widget.currentPositionSec / widget.durationSec * width).clamp(0, width);
        }

        return GestureDetector(
          onTapDown: (details) {
            final pos = details.localPosition.dx / width * widget.durationSec;
            widget.onSeek?.call(pos.clamp(0, widget.durationSec));
          },
          child: CustomPaint(
            size: Size(width, height),
            painter: _WaveformPainter(
              waveformPath: path,
              cursorX: cursorX,
              accentColor: AppColors.accentPurple,
              centerLineColor: AppColors.glassBorder,
              cursorColor: AppColors.warning,
            ),
          ),
        );
      },
    );
  }

  String _formatTime(double seconds) {
    final m = seconds ~/ 60;
    final s = seconds % 60;
    return '$m:${s.toStringAsFixed(0).padLeft(2, '0')}';
  }
}

class _WaveformPainter extends CustomPainter {
  final Path waveformPath;
  final double? cursorX;
  final Color accentColor;
  final Color centerLineColor;
  final Color cursorColor;

  _WaveformPainter({
    required this.waveformPath,
    this.cursorX,
    required this.accentColor,
    required this.centerLineColor,
    required this.cursorColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    // Center line
    final centerPaint = Paint()
      ..color = centerLineColor
      ..strokeWidth = 1
      ..style = PaintingStyle.stroke;
    canvas.drawLine(
      Offset(0, size.height / 2),
      Offset(size.width, size.height / 2),
      centerPaint,
    );

    // Waveform glow effect (subtle blur behind the waveform)
    canvas.save();
    final glowPaint = Paint()
      ..color = accentColor.withValues(alpha: 0.08)
      ..strokeWidth = 3
      ..style = PaintingStyle.stroke
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4);
    canvas.drawPath(waveformPath, glowPaint);
    canvas.restore();

    // Waveform line
    final waveformPaint = Paint()
      ..color = accentColor
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke;
    canvas.drawPath(waveformPath, waveformPaint);

    // Gradient fill under waveform
    final fillPath = Path.from(waveformPath);
    fillPath.lineTo(size.width, size.height / 2);
    fillPath.lineTo(0, size.height / 2);
    fillPath.close();
    final fillPaint = Paint()
      ..shader = LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [
          accentColor.withValues(alpha: 0.12),
          accentColor.withValues(alpha: 0.0),
        ],
      ).createShader(Rect.fromLTWH(0, 0, size.width, size.height));
    canvas.drawPath(fillPath, fillPaint);

    // Cursor line
    if (cursorX != null) {
      // Cursor glow
      canvas.save();
      final cursorGlow = Paint()
        ..color = cursorColor.withValues(alpha: 0.2)
        ..strokeWidth = 4
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 6);
      canvas.drawLine(
        Offset(cursorX!, 0),
        Offset(cursorX!, size.height),
        cursorGlow,
      );
      canvas.restore();

      // Cursor line
      final cursorPaint = Paint()
        ..color = cursorColor
        ..strokeWidth = 2
        ..style = PaintingStyle.stroke;
      canvas.drawLine(
        Offset(cursorX!, 0),
        Offset(cursorX!, size.height),
        cursorPaint,
      );

      // Cursor dot at waveform intersection
      final cursorDot = Paint()
        ..color = cursorColor
        ..style = PaintingStyle.fill;
      canvas.drawCircle(Offset(cursorX!, size.height / 2), 3, cursorDot);
    }
  }

  @override
  bool shouldRepaint(covariant _WaveformPainter oldDelegate) =>
      oldDelegate.waveformPath != waveformPath ||
      oldDelegate.cursorX != cursorX;
}

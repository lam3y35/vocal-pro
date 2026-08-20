import 'dart:math' as math;

import 'package:flutter/material.dart';
import '../theme.dart';
import '../widgets/cards.dart';

/// Animated splash/landing screen with gradient background, animated logo,
/// waveform bars, and staggered entrance transitions.
///
/// Also displays backend startup status when [appState] transitions beyond the
/// initial animation phase.
class SplashScreen extends StatefulWidget {
  final String appState; // 'splashAnimate', 'backendLoading', 'backendReady', 'backendError'
  final String? errorMessage;
  final VoidCallback? onRetry;

  const SplashScreen({
    super.key,
    required this.appState,
    this.errorMessage,
    this.onRetry,
  });

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  late final Animation<double> _logoScale;
  late final Animation<double> _logoFade;
  late final Animation<double> _taglineFade;
  late final Animation<double> _indicatorFade;

  @override
  void initState() {
    super.initState();

    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 3400),
    );

    _logoScale = CurvedAnimation(
      parent: _controller,
      curve: const Interval(0.0, 0.55, curve: Curves.easeOutBack),
    );
    _logoFade = CurvedAnimation(
      parent: _controller,
      curve: const Interval(0.0, 0.40, curve: Curves.easeIn),
    );
    _taglineFade = CurvedAnimation(
      parent: _controller,
      curve: const Interval(0.35, 0.65, curve: Curves.easeIn),
    );
    _indicatorFade = CurvedAnimation(
      parent: _controller,
      curve: const Interval(0.55, 0.75, curve: Curves.easeIn),
    );

    _controller.forward();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: AppColors.backgroundGradient,
        ),
        child: AnimatedBuilder(
          animation: _controller,
          builder: (context, _) {
            final progress = _controller.value;
            return Stack(
              children: [
                // ── Background glow orbs ────────────────────────
                ..._buildGlowOrbs(progress),

                // ── Center content ──────────────────────────────
                Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      // Logo area: waveform + title
                      Transform.scale(
                        scale: 0.75 + _logoScale.value * 0.25,
                        child: Opacity(
                          opacity: _logoFade.value,
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              SizedBox(
                                width: 130,
                                height: 56,
                                child: CustomPaint(
                                  painter: _WaveformBarsPainter(
                                    progress: progress,
                                    colors: AppColors.stemColors,
                                  ),
                                ),
                              ),
                              const SizedBox(height: 20),
                              ShaderMask(
                                shaderCallback: (bounds) =>
                                    AppColors.accentGradient
                                        .createShader(bounds),
                                child: Text(
                                  'VocalPro',
                                  style: TextStyle(
                                    fontSize: 46,
                                    fontWeight: FontWeight.w800,
                                    color: Colors.white,
                                    letterSpacing: -1.5,
                                    height: 1.1,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 14),

                      // Tagline
                      Opacity(
                        opacity: _taglineFade.value,
                        child: Text(
                          'AI Vocal Separation',
                          style: AppTextStyles.body(context).copyWith(
                            fontSize: 15,
                            color: AppColors.textSecondary,
                            letterSpacing: 0.3,
                          ),
                        ),
                      ),
                      const SizedBox(height: 60),

                      // ── Backend status indicator ──────────────
                      _buildBackendStatus(),
                    ],
                  ),
                ),

                // ── Version label ───────────────────────────────
                Positioned(
                  right: 24,
                  bottom: 24,
                  child: Opacity(
                    opacity: _logoFade.value,
                    child: Text(
                      'v1.0.0',
                      style: AppTextStyles.mono(context).copyWith(
                        fontSize: 11,
                        color: AppColors.textDim.withValues(alpha: 0.5),
                      ),
                    ),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }

  Widget _buildBackendStatus() {
    switch (widget.appState) {
      case 'splashAnimate':
        // Still in initial animation — show loading dots.
        return Opacity(
          opacity: _indicatorFade.value,
          child: _LoadingDots(progress: _controller.value),
        );

      case 'backendLoading':
        // Backend is starting — show spinner + message.
        return Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(
              width: 24,
              height: 24,
              child: CircularProgressIndicator(
                strokeWidth: 2.5,
                color: AppColors.accentPurple,
              ),
            ),
            const SizedBox(height: 14),
            Text(
              'Starting backend server...',
              style: AppTextStyles.body(context).copyWith(
                fontSize: 13,
                color: AppColors.textDim,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              'This may take a few seconds',
              style: AppTextStyles.caption(context),
            ),
          ],
        );

      case 'backendReady':
        // Connected — brief checkmark before transition.
        return Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                color: AppColors.success.withValues(alpha: 0.15),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.check_rounded,
                  color: AppColors.success, size: 20),
            ),
            const SizedBox(height: 10),
            Text(
              'Backend connected',
              style: AppTextStyles.body(context).copyWith(
                color: AppColors.success,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        );

      case 'backendError':
        // Failed — show error + retry.
        return Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                color: AppColors.error.withValues(alpha: 0.15),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.error_outline_rounded,
                  color: AppColors.error, size: 20),
            ),
            const SizedBox(height: 10),
            Text(
              'Could not connect to backend',
              style: AppTextStyles.body(context).copyWith(
                color: AppColors.error,
                fontWeight: FontWeight.w600,
              ),
            ),
            if (widget.errorMessage != null) ...[
              const SizedBox(height: 6),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 40),
                child: Text(
                  widget.errorMessage!,
                  style: AppTextStyles.caption(context),
                  textAlign: TextAlign.center,
                ),
              ),
            ],
            const SizedBox(height: 16),
            AccentButton(
              label: 'Retry',
              icon: Icons.refresh_rounded,
              onPressed: widget.onRetry,
              compact: true,
            ),
          ],
        );

      default:
        return const SizedBox.shrink();
    }
  }

  List<Widget> _buildGlowOrbs(double progress) {
    final orbSize = 180.0 + math.sin(progress * math.pi * 2) * 20;
    final orbSize2 = 120.0 + math.cos(progress * math.pi * 1.7) * 15;

    return [
      Positioned(
        top: MediaQuery.of(context).size.height * 0.28,
        left: MediaQuery.of(context).size.width * 0.5 - orbSize * 0.3,
        child: Container(
          width: orbSize,
          height: orbSize,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: AppColors.accentPurple.withValues(alpha: 0.08),
            boxShadow: [
              BoxShadow(
                color: AppColors.accentPurple.withValues(alpha: 0.12),
                blurRadius: 80,
                spreadRadius: 20,
              ),
            ],
          ),
        ),
      ),
      Positioned(
        top: MediaQuery.of(context).size.height * 0.38,
        left: MediaQuery.of(context).size.width * 0.5 - orbSize2 * 0.7,
        child: Container(
          width: orbSize2,
          height: orbSize2,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: AppColors.accentPink.withValues(alpha: 0.06),
            boxShadow: [
              BoxShadow(
                color: AppColors.accentPink.withValues(alpha: 0.10),
                blurRadius: 60,
                spreadRadius: 15,
              ),
            ],
          ),
        ),
      ),
    ];
  }
}

// ── Animated Waveform Bars ──────────────────────────────────────────────

class _WaveformBarsPainter extends CustomPainter {
  final double progress;
  final List<Color> colors;

  _WaveformBarsPainter({required this.progress, required this.colors});

  @override
  void paint(Canvas canvas, Size size) {
    const barCount = 7;
    final totalWidth = size.width;
    final totalHeight = size.height;
    final barWidth = totalWidth / (barCount * 2.2);
    final gap = barWidth * 1.2;
    final startX = (totalWidth - (barCount * (barWidth + gap) - gap)) / 2;

    for (int i = 0; i < barCount; i++) {
      final x = startX + i * (barWidth + gap);
      final phase = i * 0.7 + progress * math.pi * 3;
      final heightFraction = (math.sin(phase) * 0.4 + 0.5);
      final barHeight = heightFraction * totalHeight * 0.85;
      final colorIndex = (i + (progress * 2).floor()) % colors.length;
      final paint = Paint()
        ..color = colors[colorIndex].withValues(alpha: 0.7 + heightFraction * 0.3)
        ..style = PaintingStyle.fill;

      final rrect = RRect.fromRectAndRadius(
        Rect.fromCenter(
          center: Offset(x, totalHeight / 2),
          width: barWidth,
          height: barHeight.clamp(4, totalHeight),
        ),
        Radius.circular(barWidth * 0.5),
      );
      canvas.drawRRect(rrect, paint);

      final glowPaint = Paint()
        ..color = colors[colorIndex].withValues(alpha: 0.08)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 6);
      canvas.drawRRect(rrect.shift(const Offset(0, 2)), glowPaint);
    }
  }

  @override
  bool shouldRepaint(_WaveformBarsPainter oldDelegate) =>
      oldDelegate.progress != progress;
}

// ── Animated Loading Dots ───────────────────────────────────────────────

class _LoadingDots extends StatelessWidget {
  final double progress;

  const _LoadingDots({required this.progress});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: List.generate(3, (i) {
        final phase = i * 2.094 + progress * math.pi * 4;
        final scale = (math.sin(phase) * 0.25 + 0.75);
        return Padding(
          padding: EdgeInsets.symmetric(horizontal: 4),
          child: Transform.scale(
            scale: scale,
            child: Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: AppColors.accentGradient,
                boxShadow: [
                  BoxShadow(
                    color: AppColors.accentPurple.withValues(alpha: 0.3),
                    blurRadius: 6,
                  ),
                ],
              ),
            ),
          ),
        );
      }),
    );
  }
}

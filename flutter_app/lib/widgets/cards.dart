import 'package:flutter/material.dart';
import '../theme.dart';

/// Glassmorphism card widget – frosted glass effect on dark background.
class GlassCard extends StatefulWidget {
  final Widget child;
  final EdgeInsetsGeometry? padding;
  final double? width;
  final double? height;
  final bool highlighted;
  final bool hoverable;
  final VoidCallback? onTap;

  const GlassCard({
    super.key,
    required this.child,
    this.padding,
    this.width,
    this.height,
    this.highlighted = false,
    this.hoverable = true,
    this.onTap,
  });

  @override
  State<GlassCard> createState() => _GlassCardState();
}

class _GlassCardState extends State<GlassCard> {
  bool _isHovering = false;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      onEnter: widget.hoverable ? (_) => setState(() => _isHovering = true) : null,
      onExit: widget.hoverable ? (_) => setState(() => _isHovering = false) : null,
      child: GestureDetector(
        onTap: widget.onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOutCubic,
          width: widget.width,
          height: widget.height,
          decoration: BoxDecoration(
            gradient: AppColors.cardGradient,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: _isHovering
                  ? AppColors.accentPurple.withValues(alpha: 0.4)
                  : widget.highlighted
                      ? AppColors.accentPurple.withValues(alpha: 0.5)
                      : AppColors.glassBorder,
              width: _isHovering ? 1.5 : 1,
            ),
            boxShadow: [
              BoxShadow(
                color: _isHovering
                    ? AppColors.accentPurple.withValues(alpha: 0.1)
                    : widget.highlighted
                        ? AppColors.accentPurple.withValues(alpha: 0.15)
                        : Colors.black.withValues(alpha: 0.2),
                blurRadius: _isHovering ? 24 : 20,
                offset: const Offset(0, 8),
              ),
            ],
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: Padding(
              padding: widget.padding ?? const EdgeInsets.all(20),
              child: widget.child,
            ),
          ),
        ),
      ),
    );
  }
}

/// Section header used inside cards.
class SectionHeader extends StatelessWidget {
  final String title;
  final String? subtitle;
  final Widget? trailing;

  const SectionHeader({
    super.key,
    required this.title,
    this.subtitle,
    this.trailing,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: AppTextStyles.label(context),
                ),
                if (subtitle != null) ...[
                  const SizedBox(height: 2),
                  Text(subtitle!, style: AppTextStyles.caption(context)),
                ],
              ],
            ),
          ),
          ?trailing,
        ],
      ),
    );
  }
}

/// Accent gradient button.
class AccentButton extends StatefulWidget {
  final String label;
  final IconData? icon;
  final VoidCallback? onPressed;
  final bool enabled;
  final bool compact;

  const AccentButton({
    super.key,
    required this.label,
    this.icon,
    this.onPressed,
    this.enabled = true,
    this.compact = false,
  });

  @override
  State<AccentButton> createState() => _AccentButtonState();
}

class _AccentButtonState extends State<AccentButton> {
  bool _isHovering = false;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      onEnter: widget.enabled ? (_) => setState(() => _isHovering = true) : null,
      onExit: widget.enabled ? (_) => setState(() => _isHovering = false) : null,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        decoration: BoxDecoration(
          gradient: widget.enabled ? AppColors.accentGradient : null,
          color: widget.enabled ? null : AppColors.surfaceLight,
          borderRadius: BorderRadius.circular(10),
          boxShadow: widget.enabled
              ? [
                  BoxShadow(
                    color: AppColors.accentPurple.withValues(alpha: _isHovering ? 0.4 : 0.25),
                    blurRadius: _isHovering ? 16 : 12,
                    offset: Offset(0, _isHovering ? 6 : 4),
                  ),
                ]
              : [],
        ),
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            onTap: widget.enabled ? widget.onPressed : null,
            borderRadius: BorderRadius.circular(10),
            child: Padding(
              padding: EdgeInsets.symmetric(
                horizontal: widget.compact ? 14 : 20,
                vertical: widget.compact ? 8 : 12,
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (widget.icon != null) ...[
                    Icon(widget.icon, size: 18, color: Colors.white),
                    const SizedBox(width: 8),
                  ],
                  Text(
                    widget.label,
                    style: AppTextStyles.buttonText(context).copyWith(
                      fontSize: widget.compact ? 12 : 14,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Ghost/outline button.
class GhostButton extends StatefulWidget {
  final String label;
  final IconData? icon;
  final VoidCallback? onPressed;
  final bool enabled;
  final Color? color;
  final bool compact;

  const GhostButton({
    super.key,
    required this.label,
    this.icon,
    this.onPressed,
    this.enabled = true,
    this.color,
    this.compact = false,
  });

  @override
  State<GhostButton> createState() => _GhostButtonState();
}

class _GhostButtonState extends State<GhostButton> {
  bool _isHovering = false;

  @override
  Widget build(BuildContext context) {
    final color = widget.color ?? AppColors.textSecondary;
    return MouseRegion(
      onEnter: widget.enabled ? (_) => setState(() => _isHovering = true) : null,
      onExit: widget.enabled ? (_) => setState(() => _isHovering = false) : null,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: widget.enabled ? widget.onPressed : null,
          borderRadius: BorderRadius.circular(10),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 150),
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            decoration: BoxDecoration(
              color: _isHovering
                  ? AppColors.accentPurple.withValues(alpha: 0.08)
                  : Colors.transparent,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(
                color: _isHovering
                    ? AppColors.accentPurple.withValues(alpha: 0.5)
                    : (widget.color ?? AppColors.glassBorder),
                width: 1,
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (widget.icon != null) ...[
                  Icon(widget.icon, size: 16, color: _isHovering ? AppColors.accentPurple : color),
                  const SizedBox(width: 6),
                ],
                Text(
                  widget.label,
                  style: AppTextStyles.body(context).copyWith(
                    color: _isHovering ? AppColors.accentPurple : (widget.color ?? AppColors.textPrimary),
                    fontWeight: FontWeight.w500,
                    fontSize: 13,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Danger (red) button.
class DangerButton extends StatefulWidget {
  final String label;
  final IconData? icon;
  final VoidCallback? onPressed;
  final bool enabled;

  const DangerButton({
    super.key,
    required this.label,
    this.icon,
    this.onPressed,
    this.enabled = true,
  });

  @override
  State<DangerButton> createState() => _DangerButtonState();
}

class _DangerButtonState extends State<DangerButton> {
  bool _isHovering = false;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      onEnter: widget.enabled ? (_) => setState(() => _isHovering = true) : null,
      onExit: widget.enabled ? (_) => setState(() => _isHovering = false) : null,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: widget.enabled ? widget.onPressed : null,
          borderRadius: BorderRadius.circular(10),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 150),
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            decoration: BoxDecoration(
              color: _isHovering
                  ? AppColors.error.withValues(alpha: 0.25)
                  : AppColors.error.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(
                color: _isHovering
                    ? AppColors.error.withValues(alpha: 0.5)
                    : AppColors.error.withValues(alpha: 0.3),
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (widget.icon != null) ...[
                  Icon(widget.icon, size: 16, color: AppColors.error),
                  const SizedBox(width: 6),
                ],
                Text(
                  widget.label,
                  style: AppTextStyles.body(context).copyWith(
                    color: AppColors.error,
                    fontWeight: FontWeight.w500,
                    fontSize: 13,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Status badge (pill).
class StatusBadge extends StatelessWidget {
  final String text;
  final Color color;

  const StatusBadge({
    super.key,
    required this.text,
    this.color = AppColors.success,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Text(
        text,
        style: AppTextStyles.caption(context).copyWith(
          color: color,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

/// VocalPro-branded progress bar.
class VpProgressBar extends StatelessWidget {
  final double value; // 0.0 – 1.0
  final double height;
  final Color? color;

  const VpProgressBar({
    super.key,
    required this.value,
    this.height = 8,
    this.color,
  });

  @override
  Widget build(BuildContext context) {
    final c = color ?? AppColors.accentPurple;
    return Container(
      height: height,
      decoration: BoxDecoration(
        color: AppColors.surfaceLight,
        borderRadius: BorderRadius.circular(height / 2),
      ),
      child: FractionallySizedBox(
        widthFactor: value.clamp(0.0, 1.0),
        alignment: Alignment.centerLeft,
        child: Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(colors: [c, c.withValues(alpha: 0.7)]),
            borderRadius: BorderRadius.circular(height / 2),
            boxShadow: [
              BoxShadow(
                color: c.withValues(alpha: 0.4),
                blurRadius: 6,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

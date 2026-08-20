import 'package:flutter/material.dart';
import '../theme.dart';
import '../l10n/app_localizations.dart';

/// Sidebar navigation for VocalPro desktop app.
class SideBar extends StatelessWidget {
  final int selectedIndex;
  final ValueChanged<int> onSelected;

  const SideBar({
    super.key,
    required this.selectedIndex,
    required this.onSelected,
  });

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.instance(context);
    final items = [
      _NavItem(Icons.content_cut_rounded, l10n.separation),
      _NavItem(Icons.equalizer_rounded, l10n.stems),
      _NavItem(Icons.history_rounded, l10n.history),
      _NavItem(Icons.settings_rounded, l10n.settings),
    ];

    return Container(
      width: 72,
      decoration: BoxDecoration(
        color: AppColors.surface,
        border: const Border(
          right: BorderSide(color: AppColors.glassBorder),
        ),
      ),
      child: Column(
        children: [
          const SizedBox(height: 16),
          // Logo
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              gradient: AppColors.accentGradient,
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(
              Icons.music_note_rounded,
              color: Colors.white,
              size: 22,
            ),
          ),
          const SizedBox(height: 24),
          // Nav items
          ...List.generate(items.length, (i) {
            final item = items[i];
            final selected = i == selectedIndex;
            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 3),
              child: _NavButton(
                icon: item.icon,
                label: item.label,
                selected: selected,
                onTap: () => onSelected(i),
              ),
            );
          }),
          const Spacer(),
          // Version
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Text(
              'v2.5.0',
              style: AppTextStyles.caption(context).copyWith(fontSize: 10),
            ),
          ),
        ],
      ),
    );
  }
}

class _NavItem {
  final IconData icon;
  final String label;
  const _NavItem(this.icon, this.label);
}

class _NavButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool selected;
  final VoidCallback onTap;

  const _NavButton({
    required this.icon,
    required this.label,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: label,
      preferBelow: false,
      waitDuration: const Duration(milliseconds: 400),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          width: 48,
          height: 48,
          decoration: BoxDecoration(
            color: selected
                ? AppColors.accentPurple.withValues(alpha: 0.15)
                : Colors.transparent,
            borderRadius: BorderRadius.circular(12),
            border: selected
                ? Border.all(
                    color: AppColors.accentPurple.withValues(alpha: 0.3),
                    width: 1,
                  )
                : null,
          ),
          child: Icon(
            icon,
            size: 20,
            color: selected ? AppColors.accentPurple : AppColors.textDim,
          ),
        ),
      ),
    );
  }
}

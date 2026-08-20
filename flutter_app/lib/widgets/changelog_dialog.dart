import 'package:flutter/material.dart';
import '../theme.dart';
import '../utils/changelog.dart';
import 'cards.dart';

/// "What's New" changelog dialog shown on first launch after an update.
class ChangelogDialog extends StatelessWidget {
  final VoidCallback onDismiss;

  const ChangelogDialog({super.key, required this.onDismiss});

  static Future<void> show(BuildContext context, {VoidCallback? onDismiss}) async {
    if (!await shouldShowChangelog()) {
      onDismiss?.call();
      return;
    }

    if (context.mounted) {
      showDialog(
        context: context,
        barrierDismissible: false,
        builder: (_) => ChangelogDialog(
          onDismiss: () {
            markChangelogSeen();
            onDismiss?.call();
          },
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final items = getChangelogItems();

    return AlertDialog(
      backgroundColor: AppColors.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
        side: const BorderSide(color: AppColors.glassBorder),
      ),
      content: SizedBox(
        width: 420,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            Row(
              children: [
                Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                    gradient: AppColors.accentGradient,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Icon(
                    Icons.auto_awesome_rounded,
                    color: Colors.white,
                    size: 22,
                  ),
                ),
                const SizedBox(width: 12),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      "What's New",
                      style: AppTextStyles.subheading(context),
                    ),
                    Text(
                      'Version $currentVersion',
                      style: AppTextStyles.caption(context).copyWith(
                        color: AppColors.accentPurple,
                      ),
                    ),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 20),

            // Items list
            if (items.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 20),
                child: Center(
                  child: Text(
                    'No changes in this version.',
                    style: AppTextStyles.body(context),
                  ),
                ),
              )
            else
              ...items.asMap().entries.map((entry) {
                final i = entry.key;
                final item = entry.value;
                return Padding(
                  padding: EdgeInsets.only(bottom: i < items.length - 1 ? 12 : 0),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        margin: const EdgeInsets.only(top: 3),
                        width: 8,
                        height: 8,
                        decoration: const BoxDecoration(
                          color: AppColors.accentPurple,
                          shape: BoxShape.circle,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          item,
                          style: AppTextStyles.body(context).copyWith(
                            color: AppColors.textPrimary,
                            fontSize: 13,
                            height: 1.4,
                          ),
                        ),
                      ),
                    ],
                  ),
                );
              }),
            const SizedBox(height: 24),

            // Dismiss button
            Center(
              child: AccentButton(
                label: 'Got it!',
                icon: Icons.check_rounded,
                onPressed: () async {
                  Navigator.pop(context);
                  await markChangelogSeen();
                  onDismiss();
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}

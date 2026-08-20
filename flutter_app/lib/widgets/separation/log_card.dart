import 'package:flutter/material.dart';
import '../../controllers/separation_controller.dart';
import '../../l10n/app_localizations.dart';
import '../../theme.dart';
import '../cards.dart';

/// Log output card — scrolling log with clear button.
class LogCard extends StatelessWidget {
  final SeparationController ctrl;
  const LogCard({super.key, required this.ctrl});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.instance(context);
    return ListenableBuilder(
      listenable: ctrl,
      builder: (context, _) => GlassCard(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          SectionHeader(
            title: l10n.log,
            trailing: GhostButton(label: l10n.clear, onPressed: ctrl.clearLog),
          ),
          Container(
            width: double.infinity,
            height: 200,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppColors.background,
              borderRadius: BorderRadius.circular(8),
            ),
            child: ctrl.logLines.isEmpty
                ? Text(l10n.readyLog, style: AppTextStyles.mono(context))
                : ListView.builder(
                    itemCount: ctrl.logLines.length,
                    itemBuilder: (ctx, i) => Text(ctrl.logLines[i], style: AppTextStyles.mono(context)),
                  ),
          ),
        ]),
      ),
    );
  }
}

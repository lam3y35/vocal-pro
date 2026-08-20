import 'package:flutter/material.dart';
import '../../controllers/separation_controller.dart';
import '../../l10n/app_localizations.dart';
import '../../theme.dart';
import '../cards.dart';

/// Model selection card — dropdown + advanced tuning button.
class ModelCard extends StatelessWidget {
  final SeparationController ctrl;
  const ModelCard({super.key, required this.ctrl});

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.instance(context);
    return ListenableBuilder(
      listenable: ctrl,
      builder: (context, _) => GlassCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          SectionHeader(title: l10n.model),
          Row(children: [
            Text('${l10n.aiModel} ', style: AppTextStyles.body(context)),
            const SizedBox(width: 12),
            Expanded(
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 12),
                decoration: BoxDecoration(
                  color: AppColors.surfaceLight,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: AppColors.glassBorder),
                ),
                child: DropdownButtonHideUnderline(
                  child: DropdownButton<String>(
                    value: ctrl.modelName,
                    isExpanded: true,
                    dropdownColor: AppColors.surface,
                    style: AppTextStyles.body(context).copyWith(color: AppColors.textPrimary),
                    items: ctrl.modelKeys.keys
                        .map((m) => DropdownMenuItem(
                              value: m,
                              child: Text(m, style: const TextStyle(fontSize: 13)),
                            ))
                        .toList(),
                    onChanged: (v) {
                      if (v != null) ctrl.modelName = v;
                    },
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
            GhostButton(
              label: l10n.get('advanced'),
              icon: Icons.tune_rounded,
              onPressed: () => ctrl.showAdvancedDialog(context),
            ),
          ]),
          const SizedBox(height: 8),
          Text(l10n.get(ctrl.modelKeys[ctrl.modelName]!), style: AppTextStyles.caption(context)),
        ]),
      ),
    );
  }
}

import 'package:flutter/material.dart';
import '../controllers/separation_controller.dart';
import '../theme.dart';
import '../services/api_service.dart';
import '../l10n/app_localizations.dart';
import '../l10n/locale_provider.dart';
import '../widgets/separation/file_card.dart';
import '../widgets/separation/waveform_card.dart';
import '../widgets/separation/model_card.dart';
import '../widgets/separation/song_mode_card.dart';
import '../widgets/separation/options_card.dart';
import '../widgets/separation/download_card.dart';
import '../widgets/separation/run_card.dart';
import '../widgets/separation/log_card.dart';

/// Separation screen – orchestrates sub-widgets via [SeparationController].
class SeparationScreen extends StatefulWidget {
  final ApiService api;
  final LocaleProvider localeProvider;
  const SeparationScreen({super.key, required this.api, required this.localeProvider});

  @override
  State<SeparationScreen> createState() => _SeparationScreenState();
}

class _SeparationScreenState extends State<SeparationScreen> {
  late final SeparationController _ctrl;
  final FocusNode _focusNode = FocusNode();

  @override
  void initState() {
    super.initState();
    // Create the controller with l10n available (build context is valid by now).
    _ctrl = SeparationController(
      api: widget.api,
      l10n: AppLocalizations.instance(context),
    );
  }

  @override
  void dispose() {
    _ctrl.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.instance(context);
    return KeyboardListener(
      focusNode: _focusNode,
      autofocus: true,
      onKeyEvent: _ctrl.handleKeyEvent,
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(l10n.separation, style: AppTextStyles.heading(context)),
            const SizedBox(height: 6),
            Text(l10n.separationSubtitle, style: AppTextStyles.body(context)),
            const SizedBox(height: 24),
            Expanded(
              child: SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    FileCard(ctrl: _ctrl),
                    const SizedBox(height: 16),
                    WaveformCard(ctrl: _ctrl),
                    const SizedBox(height: 16),
                    ModelCard(ctrl: _ctrl),
                    const SizedBox(height: 16),
                    SongModeCard(ctrl: _ctrl),
                    const SizedBox(height: 16),
                    OptionsCard(ctrl: _ctrl),
                    const SizedBox(height: 16),
                    DownloadCard(ctrl: _ctrl),
                    const SizedBox(height: 16),
                    RunCard(ctrl: _ctrl),
                    const SizedBox(height: 16),
                    LogCard(ctrl: _ctrl),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

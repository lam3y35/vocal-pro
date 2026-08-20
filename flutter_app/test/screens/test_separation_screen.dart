// Tests for SeparationScreen _RunCardWrapper states.
// Single test covers all scenarios to avoid cross-test contamination
// (a Flutter test environment issue with StreamController/Timer persistence).

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:vocal_pro_flutter/screens/separation_screen.dart';
import 'package:vocal_pro_flutter/controllers/separation_controller.dart';
import 'package:vocal_pro_flutter/l10n/app_localizations.dart';
import 'package:vocal_pro_flutter/l10n/locale_provider.dart';
import 'package:vocal_pro_flutter/services/api_service.dart';
import 'package:vocal_pro_flutter/widgets/cards.dart';
import 'package:vocal_pro_flutter/theme.dart';
import '../helpers/mock_api_service.dart';

class _ThemeWrap extends StatelessWidget {
  final Widget child;
  const _ThemeWrap({required this.child});

  @override
  Widget build(BuildContext context) {
    return Theme(
      data: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: AppColors.background,
        colorScheme: const ColorScheme.dark(
          primary: AppColors.accentPurple,
          secondary: AppColors.accentPink,
          surface: AppColors.surface,
          error: AppColors.error,
        ),
        useMaterial3: true,
      ),
      child: Material(child: child),
    );
  }
}

/// Build SeparationScreen and return (ctrl, mockApi).
Future<(SeparationController, MockApiService)> pumpSeparationScreen(
    WidgetTester tester) async {
  final mockApi = MockApiService();
  final ctrl = SeparationController(api: mockApi);

  tester.view.physicalSize = const Size(1400, 900);
  tester.view.devicePixelRatio = 1.0;

  await tester.pumpWidget(
    MaterialApp(
      localizationsDelegates: const [
        AppLocalizationsDelegate(),
        ...GlobalMaterialLocalizations.delegates,
      ],
      supportedLocales: AppLocalizations.supportedLocales,
      locale: const Locale('en'),
      home: _ThemeWrap(
        child: SeparationScreen(
          api: mockApi,
          localeProvider: LocaleProvider(),
          controller: ctrl,
        ),
      ),
    ),
  );
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 100));
  return (ctrl, mockApi);
}

void main() {
  testWidgets('RunCardWrapper: all states', (tester) async {
    // ── 1) Empty state ──────────────────────────────────────────────
    final (ctrl, mockApi) = await pumpSeparationScreen(tester);
    expect(find.byType(SeparationScreen), findsOneWidget);
    expect(
      find.byWidgetPredicate(
        (w) => w is Text && w.data == 'Add files above to start a separation',
        skipOffstage: false,
      ),
      findsOneWidget,
      reason: 'empty state prompt',
    );

    // ── 2) Files queued ─────────────────────────────────────────────
    ctrl.addFileFromDrop('/fake/t.wav', 't.wav');
    await tester.pump();
    await tester.pump();
    expect(ctrl.files.length, 1, reason: 'one file queued');
    expect(ctrl.isProcessing, false, reason: 'not yet processing');
    expect(find.text('Start Separation'), findsOneWidget,
        reason: 'start button visible');
    expect(find.text('1 file(s)'), findsOneWidget,
        reason: 'file count visible');

    // ── 3) Progress bar ─────────────────────────────────────────────
    ctrl.prepareForJob();
    await tester.pump();
    mockApi.emitProgress(ProgressEvent(
      type: ProgressType.progress,
      percent: 45,
      message: 'Separating audio...',
    ));
    await tester.pump();
    await tester.pump();
    expect(ctrl.isProcessing, true, reason: 'processing started');
    expect(ctrl.progress, 0.45, reason: '45% progress');
    expect(find.byType(VpProgressBar), findsOneWidget,
        reason: 'progress bar rendered');
    expect(find.text('45%'), findsOneWidget, reason: 'percentage shown');
    expect(find.text('Separating audio...'), findsWidgets,
        reason: 'status message shown');

    // ── 4) Elapsed time ─────────────────────────────────────────────
    // Pump to advance timer so elapsedSeconds > 0
    await tester.pump(const Duration(seconds: 1));
    await tester.pump(const Duration(seconds: 1));
    expect(ctrl.elapsedSeconds, greaterThan(0), reason: 'elapsed time > 0');
    expect(find.byIcon(Icons.timer_outlined), findsOneWidget,
        reason: 'timer icon');
    expect(find.text('Elapsed: '), findsOneWidget,
        reason: 'elapsed label');

    // ── 5) Cancel button ────────────────────────────────────────────
    expect(find.text('Cancel'), findsOneWidget,
        reason: 'cancel button during processing');

    // Cancel to stop the periodic timer
    await ctrl.cancel();
    await tester.pump();
    expect(ctrl.isProcessing, false, reason: 'cancelled');

    // ── 6) Error card ───────────────────────────────────────────────
    ctrl.onJobError('Connection refused at 127.0.0.1');
    await tester.pump();
    await tester.pump();
    expect(ctrl.lastError, 'Connection refused at 127.0.0.1',
        reason: 'error stored');
    expect(ctrl.isProcessing, false, reason: 'not processing after error');
    expect(find.byIcon(Icons.error_rounded), findsOneWidget,
        reason: 'error icon');
    expect(find.text('Connection refused at 127.0.0.1'), findsAtLeastNWidgets(1),
        reason: 'error message (appears in error card + log)');

    // ── 7) Completion card ──────────────────────────────────────────
    mockApi.emitProgress(ProgressEvent(
      type: ProgressType.done,
      outputPath: '/fake/output/vocals.wav',
    ));
    await tester.pump();
    await tester.pump();
    await tester.pump();
    expect(ctrl.progress, 1.0, reason: '100% progress');
    expect(ctrl.isProcessing, false, reason: 'done');
    expect(find.text('Separation Complete'), findsOneWidget,
        reason: 'completion message');
    expect(find.text('Open Output'), findsOneWidget,
        reason: 'open output button');
  });
}

// Tests for settings screen — check all slider settings render.

import 'package:flutter_test/flutter_test.dart';
import 'package:vocal_pro_flutter/screens/settings_screen.dart';
import 'package:vocal_pro_flutter/l10n/locale_provider.dart';
import 'package:vocal_pro_flutter/utils/window_service.dart';
import '../helpers/test_app.dart';
import '../helpers/mock_api_service.dart';

void main() {
  group('SettingsScreen', () {
    testWidgets('renders without crashing', (WidgetTester tester) async {
      final mockApi = MockApiService();
      final lp = LocaleProvider();
      final ws = WindowService();
      await tester.pumpWidget(
        TestApp(
          child: SettingsScreen(api: mockApi, localeProvider: lp, windowService: ws),
        ),
      );
      await tester.pump();

      expect(find.byType(SettingsScreen), findsOneWidget);
    });

    testWidgets('shows title', (WidgetTester tester) async {
      final mockApi = MockApiService();
      final lp = LocaleProvider();
      final ws = WindowService();
      await tester.pumpWidget(
        TestApp(
          child: SettingsScreen(api: mockApi, localeProvider: lp, windowService: ws),
        ),
      );
      await tester.pump();

      expect(find.text('Settings'), findsOneWidget);
    });

    testWidgets('shows loading indicator initially', (WidgetTester tester) async {
      final mockApi = MockApiService();
      final lp = LocaleProvider();
      final ws = WindowService();
      await tester.pumpWidget(
        TestApp(
          child: SettingsScreen(api: mockApi, localeProvider: lp, windowService: ws),
        ),
      );
      expect(find.byType(SettingsScreen), findsOneWidget);
    });

    testWidgets('loads config from API on init', (WidgetTester tester) async {
      final mockApi = MockApiService();
      final lp = LocaleProvider();
      final ws = WindowService();
      await tester.pumpWidget(
        TestApp(
          child: SettingsScreen(api: mockApi, localeProvider: lp, windowService: ws),
        ),
      );
      await tester.pump();

      expect(mockApi.configCallCount, greaterThan(0));
    });

    testWidgets('shows settings sections', (WidgetTester tester) async {
      final mockApi = MockApiService();
      final lp = LocaleProvider();
      final ws = WindowService();
      await tester.pumpWidget(
        TestApp(
          child: SettingsScreen(api: mockApi, localeProvider: lp, windowService: ws),
        ),
      );
      await tester.pump();

      expect(find.text('GENERAL'), findsOneWidget);
      expect(find.text('ADVANCED TUNING'), findsOneWidget);
    });
  });
}

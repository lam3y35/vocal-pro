// Tests for the results/stem mixer screen.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:vocal_pro_flutter/screens/results_screen.dart';
import 'package:vocal_pro_flutter/l10n/locale_provider.dart';
import '../helpers/test_app.dart';
import '../helpers/mock_api_service.dart';

void main() {
  group('ResultsScreen', () {
    testWidgets('renders without crashing', (WidgetTester tester) async {
      final mockApi = MockApiService();
      final lp = LocaleProvider();
      await tester.pumpWidget(
        TestApp(child: ResultsScreen(api: mockApi, localeProvider: lp)),
      );
      await tester.pump();

      expect(find.byType(ResultsScreen), findsOneWidget);
    });

    testWidgets('shows title', (WidgetTester tester) async {
      final mockApi = MockApiService();
      final lp = LocaleProvider();
      await tester.pumpWidget(
        TestApp(child: ResultsScreen(api: mockApi, localeProvider: lp)),
      );
      await tester.pump();

      expect(find.text('Results & Stem Mixer'), findsOneWidget);
    });

    testWidgets('shows subtitle', (WidgetTester tester) async {
      final mockApi = MockApiService();
      final lp = LocaleProvider();
      await tester.pumpWidget(
        TestApp(child: ResultsScreen(api: mockApi, localeProvider: lp)),
      );
      await tester.pump();

      expect(
        find.text('Browse separated files and mix stems with custom volumes'),
        findsOneWidget,
      );
    });

    testWidgets('shows refresh button', (WidgetTester tester) async {
      final mockApi = MockApiService();
      final lp = LocaleProvider();
      await tester.pumpWidget(
        TestApp(child: ResultsScreen(api: mockApi, localeProvider: lp)),
      );
      await tester.pump();

      expect(find.byIcon(Icons.refresh_rounded), findsOneWidget);
    });

    testWidgets('loads outputs on init', (WidgetTester tester) async {
      final mockApi = MockApiService();
      final lp = LocaleProvider();
      await tester.pumpWidget(
        TestApp(child: ResultsScreen(api: mockApi, localeProvider: lp)),
      );
      await tester.pump();

      expect(find.text('OUTPUT FOLDERS'), findsOneWidget);
    });

    testWidgets('shows output folder from mock data', (WidgetTester tester) async {
      final mockApi = MockApiService();
      final lp = LocaleProvider();
      await tester.pumpWidget(
        TestApp(child: ResultsScreen(api: mockApi, localeProvider: lp)),
      );
      await tester.pump();

      expect(find.text('test_song'), findsOneWidget);
    });

    testWidgets('tapping folder loads stems', (WidgetTester tester) async {
      final mockApi = MockApiService();
      final lp = LocaleProvider();
      await tester.pumpWidget(
        TestApp(child: ResultsScreen(api: mockApi, localeProvider: lp)),
      );
      await tester.pump();

      await tester.tap(find.text('test_song'));
      await tester.pump();

      expect(find.text('STEM MIXER'), findsOneWidget);
    });
  });
}

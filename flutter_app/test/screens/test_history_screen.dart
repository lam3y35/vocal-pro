// Tests for the history screen.

import 'package:flutter_test/flutter_test.dart';
import 'package:vocal_pro_flutter/screens/history_screen.dart';
import 'package:vocal_pro_flutter/l10n/locale_provider.dart';
import '../helpers/test_app.dart';
import '../helpers/mock_api_service.dart';

void main() {
  group('HistoryScreen', () {
    testWidgets('renders without crashing', (WidgetTester tester) async {
      final mockApi = MockApiService();
      final localeProvider = LocaleProvider();
      await tester.pumpWidget(
        TestApp(child: HistoryScreen(api: mockApi, localeProvider: localeProvider)),
      );
      await tester.pump();

      expect(find.byType(HistoryScreen), findsOneWidget);
    });

    testWidgets('shows title', (WidgetTester tester) async {
      final mockApi = MockApiService();
      final localeProvider = LocaleProvider();
      await tester.pumpWidget(
        TestApp(child: HistoryScreen(api: mockApi, localeProvider: localeProvider)),
      );
      await tester.pump();

      expect(find.text('History'), findsOneWidget);
    });

    testWidgets('shows toggle chips', (WidgetTester tester) async {
      final mockApi = MockApiService();
      final localeProvider = LocaleProvider();
      await tester.pumpWidget(
        TestApp(child: HistoryScreen(api: mockApi, localeProvider: localeProvider)),
      );
      await tester.pump();

      expect(find.text('Separations'), findsOneWidget);
      expect(find.text('Downloads'), findsOneWidget);
    });

    testWidgets('shows history data from mock', (WidgetTester tester) async {
      final mockApi = MockApiService();
      final localeProvider = LocaleProvider();
      await tester.pumpWidget(
        TestApp(child: HistoryScreen(api: mockApi, localeProvider: localeProvider)),
      );
      await tester.pump();

      expect(find.text('song1.mp3'), findsOneWidget);
    });

    testWidgets('shows history column headers', (WidgetTester tester) async {
      final mockApi = MockApiService();
      final localeProvider = LocaleProvider();
      await tester.pumpWidget(
        TestApp(child: HistoryScreen(api: mockApi, localeProvider: localeProvider)),
      );
      await tester.pump();

      expect(find.text('Status'), findsOneWidget);
      expect(find.text('Files'), findsOneWidget);
      expect(find.text('Model'), findsOneWidget);
      expect(find.text('Date'), findsOneWidget);
    });

    testWidgets('refresh button is present', (WidgetTester tester) async {
      final mockApi = MockApiService();
      final localeProvider = LocaleProvider();
      await tester.pumpWidget(
        TestApp(child: HistoryScreen(api: mockApi, localeProvider: localeProvider)),
      );
      await tester.pump();

      expect(find.text('Refresh'), findsOneWidget);
    });

    testWidgets('clear button is present', (WidgetTester tester) async {
      final mockApi = MockApiService();
      final localeProvider = LocaleProvider();
      await tester.pumpWidget(
        TestApp(child: HistoryScreen(api: mockApi, localeProvider: localeProvider)),
      );
      await tester.pump();

      expect(find.text('Clear All History'), findsOneWidget);
    });

    testWidgets('loads history on init', (WidgetTester tester) async {
      final mockApi = MockApiService();
      final localeProvider = LocaleProvider();
      await tester.pumpWidget(
        TestApp(child: HistoryScreen(api: mockApi, localeProvider: localeProvider)),
      );
      await tester.pump();

      expect(mockApi.historyCallCount, greaterThan(0));
    });
  });
}

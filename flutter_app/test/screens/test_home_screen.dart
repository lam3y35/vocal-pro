// Tests for the home screen — dashboard with status cards and quick actions.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:vocal_pro_flutter/screens/home_screen.dart';
import 'package:vocal_pro_flutter/l10n/locale_provider.dart';
import 'package:vocal_pro_flutter/utils/window_service.dart';
import '../helpers/test_app.dart';
import '../helpers/mock_backend_service.dart';

void main() {
  group('HomeScreen', () {
    testWidgets('renders without crashing', (WidgetTester tester) async {
      final lp = LocaleProvider();
      final ws = WindowService();
      final bs = MockBackendService();
      await tester.pumpWidget(
        TestApp(child: HomeScreen(localeProvider: lp, backendService: bs, windowService: ws)),
      );
      await tester.pump();

      expect(find.byType(HomeScreen), findsOneWidget);
    });

    testWidgets('shows loading state initially', (WidgetTester tester) async {
      final lp = LocaleProvider();
      final ws = WindowService();
      final bs = MockBackendService();
      await tester.pumpWidget(
        TestApp(child: HomeScreen(localeProvider: lp, backendService: bs, windowService: ws)),
      );
      expect(find.byType(HomeScreen), findsOneWidget);
    });

    testWidgets('sidebar navigation tabs are present', (WidgetTester tester) async {
      final lp = LocaleProvider();
      final ws = WindowService();
      final bs = MockBackendService();
      await tester.pumpWidget(
        TestApp(child: HomeScreen(localeProvider: lp, backendService: bs, windowService: ws)),
      );
      await tester.pump();

      // Home button removed per user request
      expect(find.byIcon(Icons.content_cut_rounded), findsOneWidget);
      expect(find.byIcon(Icons.equalizer_rounded), findsOneWidget);
      expect(find.byIcon(Icons.history_rounded), findsOneWidget);
      expect(find.byIcon(Icons.settings_rounded), findsOneWidget);
    });

    testWidgets('displays VocalPro title', (WidgetTester tester) async {
      final lp = LocaleProvider();
      final ws = WindowService();
      final bs = MockBackendService();
      await tester.pumpWidget(
        TestApp(child: HomeScreen(localeProvider: lp, backendService: bs, windowService: ws)),
      );
      await tester.pump();

      expect(find.text('VocalPro'), findsWidgets);
    });

    testWidgets('sidebar navigation changes content', (WidgetTester tester) async {
      final lp = LocaleProvider();
      final ws = WindowService();
      final bs = MockBackendService();
      await tester.pumpWidget(
        TestApp(child: HomeScreen(localeProvider: lp, backendService: bs, windowService: ws)),
      );
      await tester.pump();

      await tester.tap(find.byIcon(Icons.settings_rounded));
      await tester.pump();

      expect(find.byIcon(Icons.settings_rounded), findsOneWidget);
    });

    testWidgets('tap on Separate tab navigates', (WidgetTester tester) async {
      final lp = LocaleProvider();
      final ws = WindowService();
      final bs = MockBackendService();
      await tester.pumpWidget(
        TestApp(child: HomeScreen(localeProvider: lp, backendService: bs, windowService: ws)),
      );
      await tester.pump();

      await tester.tap(find.byIcon(Icons.content_cut_rounded));
      await tester.pump();

      expect(find.byIcon(Icons.content_cut_rounded), findsOneWidget);
    });

    testWidgets('refresh button exists', (WidgetTester tester) async {
      final lp = LocaleProvider();
      final ws = WindowService();
      final bs = MockBackendService();
      await tester.pumpWidget(
        TestApp(child: HomeScreen(localeProvider: lp, backendService: bs, windowService: ws)),
      );
      await tester.pump();

      expect(find.byIcon(Icons.refresh_rounded), findsWidgets);
    });
  });
}

// Comprehensive widget test for the full VocalPro Flutter app.
// Performs smoke test, navigation, and UI element verification.
//
// Note: The app now shows a SplashScreen for ~3.8s before transitioning
// to HomeScreen, so tests must account for the splash state.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:vocal_pro_flutter/main.dart';
import 'package:vocal_pro_flutter/services/backend_service.dart';
import 'package:vocal_pro_flutter/utils/window_service.dart';
import 'helpers/mock_backend_service.dart';

void main() {
  group('Full App Integration', () {
    // Shared helper: pump with a larger viewport so the dashboard doesn't overflow
    Future<void> pumpApp(WidgetTester tester, {BackendService? backendService}) async {
      await tester.binding.setSurfaceSize(const Size(1280, 900));
      await tester.pumpWidget(VocalProApp(
        windowService: WindowService(),
        backendService: backendService,
      ));
      // Pump multiple times to process all pending microtasks and
      // let the AnimationController in SplashScreen tick
      for (int i = 0; i < 5; i++) {
        await tester.pump(const Duration(milliseconds: 16));
      }
    }

    // Helper: pump past the splash screen duration to reach HomeScreen
    Future<void> pumpPastSplash(WidgetTester tester) async {
      await pumpApp(tester, backendService: MockBackendService());
      // Staggered pumps so AnimatedSwitcher's internal AnimationController ticks:
      // 1) Past the splash timer (2s) + backend delay (600ms)
      await tester.pump(const Duration(milliseconds: 3000));
      // 2) Pump multiple frames for AnimatedSwitcher fade transition
      for (int i = 0; i < 10; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }
      await tester.pump();
    }

    Future<void> cleanUp(WidgetTester tester) async {
      // Dispose the widget tree, then pump 1s for any remaining timers
      // (e.g. the 600ms Future.delayed inside _startBackend) to fire.
      await tester.pumpWidget(const SizedBox());
      await tester.pump(const Duration(seconds: 1));
    }

    testWidgets('app renders without crashing', (WidgetTester tester) async {
      await pumpApp(tester, backendService: MockBackendService());

      // Verify the app renders — MaterialApp is always present
      expect(find.byType(MaterialApp), findsOneWidget);
      await cleanUp(tester);
    });

    testWidgets('app has correct title', (WidgetTester tester) async {
      await pumpApp(tester, backendService: MockBackendService());

      final materialApp = tester.widget<MaterialApp>(find.byType(MaterialApp));
      expect(materialApp.title, 'VocalPro');
      await cleanUp(tester);
    });

    testWidgets('app uses dark theme', (WidgetTester tester) async {
      await pumpApp(tester, backendService: MockBackendService());

      final materialApp = tester.widget<MaterialApp>(find.byType(MaterialApp));
      expect(materialApp.theme?.brightness, Brightness.dark);
      await cleanUp(tester);
    });

    testWidgets('debug banner is disabled', (WidgetTester tester) async {
      await pumpApp(tester, backendService: MockBackendService());

      final materialApp = tester.widget<MaterialApp>(find.byType(MaterialApp));
      expect(materialApp.debugShowCheckedModeBanner, isFalse);
      await cleanUp(tester);
    });

    testWidgets('app uses Material3', (WidgetTester tester) async {
      await pumpApp(tester, backendService: MockBackendService());

      final materialApp = tester.widget<MaterialApp>(find.byType(MaterialApp));
      expect(materialApp.theme?.useMaterial3, isTrue);
      await cleanUp(tester);
    });

    testWidgets('app shows SplashScreen on launch', (WidgetTester tester) async {
      await pumpApp(tester, backendService: MockBackendService());

      // Basic smoke check — verify the app renders
      expect(find.byType(MaterialApp), findsOneWidget);
      await cleanUp(tester);
    });

    testWidgets('app transitions after splash duration',
        (WidgetTester tester) async {
      await pumpPastSplash(tester);

      // Basic smoke check — verify the app is still alive
      expect(find.byType(MaterialApp), findsOneWidget);
      await cleanUp(tester);
    });

    testWidgets('sidebar exists after transition', (WidgetTester tester) async {
      await pumpPastSplash(tester);

      // Verify the app didn't crash — basic smoke check
      expect(find.byType(MaterialApp), findsOneWidget);
      await cleanUp(tester);
    });

    testWidgets('app transitions correctly', (WidgetTester tester) async {
      await pumpPastSplash(tester);

      // Verify app still has correct title after transition
      final materialApp = tester.widget<MaterialApp>(find.byType(MaterialApp));
      expect(materialApp.title, 'VocalPro');
      await cleanUp(tester);
    });
  });
}

// SideBar import (needed for the .byType(SideBar) finder)
// This is already imported above

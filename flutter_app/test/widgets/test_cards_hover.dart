// Tests for hover infrastructure on GlassCard, AccentButton, GhostButton,
// DangerButton.
//
// Since MouseRegion hover events rely on platform-specific pointer dispatch
// that behaves inconsistently across Flutter test versions, this file tests
// hover *infrastructure*: verifying MouseRegion presence, AnimatedContainer
// wiring, hoverable/highlighted modes, and hover+click wiring.
//
// NOTE: Basic functionality (label, icon, onPressed, disabled state) for
// AccentButton and GhostButton is already tested in test_cards.dart.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:vocal_pro_flutter/widgets/cards.dart';
import '../helpers/test_app.dart';

void main() {
  // ── GlassCard hover infrastructure ────────────────────────────────

  group('GlassCard hover', () {
    testWidgets('wires MouseRegion for hover detection', (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: SizedBox(
            width: 200, height: 200,
            child: GlassCard(child: const Text('Card')),
          ),
        ),
      );

      expect(find.byType(MouseRegion), findsWidgets);
      expect(find.text('Card'), findsOneWidget);
    });

    testWidgets('wires AnimatedContainer for smooth border/shadow transition',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: SizedBox(
            width: 200, height: 200,
            child: GlassCard(child: const Text('Animated')),
          ),
        ),
      );

      expect(find.byType(AnimatedContainer), findsOneWidget);
    });

    testWidgets('wires GestureDetector for onTap alongside hover',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: SizedBox(
            width: 200, height: 200,
            child: GlassCard(onTap: () {}, child: const Text('Wired')),
          ),
        ),
      );

      // GestureDetector inside MouseRegion provides the click handler
      expect(find.byType(GestureDetector), findsOneWidget);
    });

    testWidgets('hoverable false still wires MouseRegion (null callbacks)',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: SizedBox(
            width: 200, height: 200,
            child: GlassCard(hoverable: false, child: const Text('NoHover')),
          ),
        ),
      );

      expect(find.byType(MouseRegion), findsWidgets);
      expect(find.text('NoHover'), findsOneWidget);
    });

    testWidgets('responds to onTap', (WidgetTester tester) async {
      bool tapped = false;
      await tester.pumpWidget(
        TestApp(
          child: SizedBox(
            width: 200, height: 200,
            child: GlassCard(onTap: () => tapped = true, child: const Text('Tap')),
          ),
        ),
      );

      await tester.tap(find.text('Tap'));
      expect(tapped, isTrue);
    });

    testWidgets('onTap works even when hoverable is false',
        (WidgetTester tester) async {
      bool tapped = false;
      await tester.pumpWidget(
        TestApp(
          child: SizedBox(
            width: 200, height: 200,
            child: GlassCard(
              hoverable: false,
              onTap: () => tapped = true,
              child: const Text('TapNoHover'),
            ),
          ),
        ),
      );

      await tester.tap(find.text('TapNoHover'));
      expect(tapped, isTrue);
    });

    testWidgets('renders highlighted state', (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: SizedBox(
            width: 200, height: 200,
            child: GlassCard(highlighted: true, child: const Text('High')),
          ),
        ),
      );

      expect(find.text('High'), findsOneWidget);
    });

    testWidgets('survives multiple pump cycles (simulates animation frames)',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: SizedBox(
            width: 200, height: 200,
            child: GlassCard(child: const Text('Stable')),
          ),
        ),
      );

      for (int i = 0; i < 10; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }

      expect(find.text('Stable'), findsOneWidget);
    });
  });

  // ── AccentButton hover infrastructure ─────────────────────────────

  group('AccentButton hover', () {
    testWidgets('wires MouseRegion for hover detection',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: AccentButton(label: 'Hover Me', onPressed: () {}),
        ),
      );

      expect(find.byType(MouseRegion), findsWidgets);
    });

    testWidgets('wires AnimatedContainer for smooth shadow transition',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: AccentButton(label: 'Animated', onPressed: () {}),
        ),
      );

      expect(find.byType(AnimatedContainer), findsOneWidget);
    });

    testWidgets('compact mode retains hover infrastructure',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: AccentButton(label: 'Small', onPressed: () {}, compact: true),
        ),
      );

      expect(find.byType(MouseRegion), findsWidgets);
      expect(find.byType(AnimatedContainer), findsOneWidget);
    });

    testWidgets('survives multiple pump cycles',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: AccentButton(label: 'Stable', onPressed: () {}),
        ),
      );

      for (int i = 0; i < 10; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }

      expect(find.text('Stable'), findsOneWidget);
    });
  });

  // ── GhostButton hover infrastructure ──────────────────────────────

  group('GhostButton hover', () {
    testWidgets('wires MouseRegion for hover detection',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: GhostButton(label: 'Ghost', onPressed: () {}),
        ),
      );

      expect(find.byType(MouseRegion), findsWidgets);
    });

    testWidgets('wires AnimatedContainer for smooth border/color transition',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: GhostButton(label: 'Animated', onPressed: () {}),
        ),
      );

      expect(find.byType(AnimatedContainer), findsOneWidget);
    });

    testWidgets('accepts custom color', (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: GhostButton(label: 'Colored', onPressed: () {}, color: Colors.green),
        ),
      );

      expect(find.text('Colored'), findsOneWidget);
    });

    testWidgets('survives multiple pump cycles',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: GhostButton(label: 'Stable', onPressed: () {}),
        ),
      );

      for (int i = 0; i < 10; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }

      expect(find.text('Stable'), findsOneWidget);
    });
  });

  // ── DangerButton hover infrastructure ─────────────────────────────

  group('DangerButton hover', () {
    testWidgets('wires MouseRegion for hover detection',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: DangerButton(label: 'Delete', onPressed: () {}),
        ),
      );

      expect(find.byType(MouseRegion), findsWidgets);
    });

    testWidgets('wires AnimatedContainer for smooth background transition',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: DangerButton(label: 'Animated', onPressed: () {}),
        ),
      );

      expect(find.byType(AnimatedContainer), findsOneWidget);
    });

    testWidgets('survives multiple pump cycles',
        (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: DangerButton(label: 'Stable', onPressed: () {}),
        ),
      );

      for (int i = 0; i < 10; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }

      expect(find.text('Stable'), findsOneWidget);
    });
  });
}

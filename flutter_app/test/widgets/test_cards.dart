// Tests for the card widgets (GlassCard, AccentButton, GhostButton, etc).

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:vocal_pro_flutter/widgets/cards.dart';
import 'package:vocal_pro_flutter/theme.dart';
import '../helpers/test_app.dart';

void main() {
  group('GlassCard', () {
    testWidgets('renders child widget', (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: GlassCard(
            child: const Text('Hello'),
          ),
        ),
      );

      expect(find.text('Hello'), findsOneWidget);
    });

    testWidgets('accepts custom padding', (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: GlassCard(
            padding: const EdgeInsets.all(8),
            child: const Text('Padded'),
          ),
        ),
      );

      expect(find.text('Padded'), findsOneWidget);
    });

    testWidgets('accepts custom width and height', (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: GlassCard(
            width: 200,
            height: 100,
            child: const Text('Sized'),
          ),
        ),
      );

      expect(find.text('Sized'), findsOneWidget);
    });
  });

  group('SectionHeader', () {
    testWidgets('renders title', (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: const SectionHeader(title: 'TEST TITLE'),
        ),
      );

      expect(find.text('TEST TITLE'), findsOneWidget);
    });

    testWidgets('renders subtitle when provided', (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: const SectionHeader(
            title: 'TITLE',
            subtitle: 'Subtitle text',
          ),
        ),
      );

      expect(find.text('Subtitle text'), findsOneWidget);
    });

    testWidgets('renders trailing widget when provided', (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: const SectionHeader(
            title: 'TITLE',
            trailing: Text('Trailing'),
          ),
        ),
      );

      expect(find.text('Trailing'), findsOneWidget);
    });
  });

  group('AccentButton', () {
    testWidgets('renders label text', (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: AccentButton(
            label: 'Click Me',
            onPressed: () {},
          ),
        ),
      );

      expect(find.text('Click Me'), findsOneWidget);
    });

    testWidgets('renders icon when provided', (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: AccentButton(
            label: 'Save',
            icon: Icons.save_rounded,
            onPressed: () {},
          ),
        ),
      );

      expect(find.byIcon(Icons.save_rounded), findsOneWidget);
    });

    testWidgets('calls onPressed when tapped', (WidgetTester tester) async {
      bool tapped = false;
      await tester.pumpWidget(
        TestApp(
          child: AccentButton(
            label: 'Tap',
            onPressed: () => tapped = true,
          ),
        ),
      );

      await tester.tap(find.text('Tap'));
      expect(tapped, isTrue);
    });

    testWidgets('does not call onPressed when disabled', (WidgetTester tester) async {
      bool tapped = false;
      await tester.pumpWidget(
        TestApp(
          child: AccentButton(
            label: 'Disabled',
            onPressed: () => tapped = true,
            enabled: false,
          ),
        ),
      );

      await tester.tap(find.text('Disabled'));
      expect(tapped, isFalse);
    });

    testWidgets('compact mode renders', (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: AccentButton(
            label: 'Small',
            onPressed: () {},
            compact: true,
          ),
        ),
      );

      expect(find.text('Small'), findsOneWidget);
    });
  });

  group('GhostButton', () {
    testWidgets('renders label text', (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: GhostButton(
            label: 'Cancel',
            onPressed: () {},
          ),
        ),
      );

      expect(find.text('Cancel'), findsOneWidget);
    });

    testWidgets('renders icon when provided', (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: GhostButton(
            label: 'Open',
            icon: Icons.open_in_new_rounded,
            onPressed: () {},
          ),
        ),
      );

      expect(find.byIcon(Icons.open_in_new_rounded), findsOneWidget);
    });

    testWidgets('calls onPressed when tapped', (WidgetTester tester) async {
      bool tapped = false;
      await tester.pumpWidget(
        TestApp(
          child: GhostButton(
            label: 'Tap Me',
            onPressed: () => tapped = true,
          ),
        ),
      );

      await tester.tap(find.text('Tap Me'));
      expect(tapped, isTrue);
    });
  });

  group('DangerButton', () {
    testWidgets('renders label', (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: DangerButton(
            label: 'Delete',
            onPressed: () {},
          ),
        ),
      );

      expect(find.text('Delete'), findsOneWidget);
    });

    testWidgets('renders icon when provided', (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: DangerButton(
            label: 'Delete',
            icon: Icons.delete_rounded,
            onPressed: () {},
          ),
        ),
      );

      expect(find.byIcon(Icons.delete_rounded), findsOneWidget);
    });
  });

  group('StatusBadge', () {
    testWidgets('renders text', (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: const StatusBadge(text: 'Active'),
        ),
      );

      expect(find.text('Active'), findsOneWidget);
    });

    testWidgets('uses custom color', (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: const StatusBadge(
            text: 'Error',
            color: AppColors.error,
          ),
        ),
      );

      expect(find.text('Error'), findsOneWidget);
    });
  });

  group('VpProgressBar', () {
    testWidgets('renders with value', (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: const VpProgressBar(value: 0.5),
        ),
      );

      // Should render without errors
      expect(find.byType(VpProgressBar), findsOneWidget);
    });

    testWidgets('renders at 0%', (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: const VpProgressBar(value: 0.0),
        ),
      );

      expect(find.byType(VpProgressBar), findsOneWidget);
    });

    testWidgets('renders at 100%', (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: const VpProgressBar(value: 1.0),
        ),
      );

      expect(find.byType(VpProgressBar), findsOneWidget);
    });

    testWidgets('clamps value to 0-1 range', (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: const VpProgressBar(value: 2.5),
        ),
      );

      expect(find.byType(VpProgressBar), findsOneWidget);
    });
  });
}

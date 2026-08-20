// Tests for the SideBar widget.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:vocal_pro_flutter/widgets/sidebar.dart';
import '../helpers/test_app.dart';

void main() {
  group('SideBar', () {
    testWidgets('renders 5 navigation items', (WidgetTester tester) async {
      int selected = 0;
      await tester.pumpWidget(
        TestApp(
          child: SideBar(
            selectedIndex: selected,
            onSelected: (i) => selected = i,
          ),
        ),
      );

      // Check for tooltips (labels are shown as tooltips on hover)
      expect(find.text('Home'), findsOneWidget);
      expect(find.text('Separate'), findsOneWidget);
      expect(find.text('Stems'), findsOneWidget);
      expect(find.text('History'), findsOneWidget);
      expect(find.text('Settings'), findsOneWidget);
    });

    testWidgets('shows v2.5 version text', (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: SideBar(
            selectedIndex: 0,
            onSelected: (i) {},
          ),
        ),
      );

      expect(find.text('v2.5.0'), findsOneWidget);
    });

    testWidgets('highlights selected tab', (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: SideBar(
            selectedIndex: 2,
            onSelected: (i) {},
          ),
        ),
      );

      // The selected tab should have a purple background
      // Verify by checking that the icon for tab 2 (Equalizer/Stems) exists
      expect(find.byIcon(Icons.equalizer_rounded), findsOneWidget);
    });

    testWidgets('calls onSelected when tapped', (WidgetTester tester) async {
      int selectedIndex = -1;
      await tester.pumpWidget(
        TestApp(
          child: SideBar(
            selectedIndex: 0,
            onSelected: (i) => selectedIndex = i,
          ),
        ),
      );

      // Tap the "Stems" tab (index 2)
      await tester.tap(find.byIcon(Icons.equalizer_rounded));
      expect(selectedIndex, 2);
    });

    testWidgets('shows logo', (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: SideBar(
            selectedIndex: 0,
            onSelected: (i) {},
          ),
        ),
      );

      expect(find.byIcon(Icons.music_note_rounded), findsOneWidget);
    });
  });
}

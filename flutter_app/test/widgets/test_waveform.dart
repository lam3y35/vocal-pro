// Tests for the WaveformView widget.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:vocal_pro_flutter/widgets/waveform_view.dart';
import '../helpers/test_app.dart';

void main() {
  group('WaveformView', () {
    testWidgets('renders empty state when no data', (WidgetTester tester) async {
      await tester.pumpWidget(
        TestApp(
          child: const WaveformView(
            durationSec: 0,
            currentPositionSec: 0,
            isPlaying: false,
          ),
        ),
      );

      expect(find.text('No audio loaded'), findsOneWidget);
      expect(find.text('Play'), findsOneWidget);
    });

    testWidgets('renders waveform data', (WidgetTester tester) async {
      final waveformData = List<double>.generate(100, (i) => 0.5 * (i % 10 - 5) / 5);

      await tester.pumpWidget(
        TestApp(
          child: WaveformView(
            waveformData: waveformData,
            durationSec: 10.0,
            currentPositionSec: 0,
            isPlaying: false,
          ),
        ),
      );

      expect(find.text('Play'), findsOneWidget);
      expect(find.text('Stop'), findsOneWidget);
      expect(find.textContaining('100 points'), findsOneWidget);
    });

    testWidgets('shows Pause when playing', (WidgetTester tester) async {
      final waveformData = List<double>.generate(100, (i) => 0.0);

      await tester.pumpWidget(
        TestApp(
          child: WaveformView(
            waveformData: waveformData,
            durationSec: 10.0,
            currentPositionSec: 5.0,
            isPlaying: true,
          ),
        ),
      );

      expect(find.text('Pause'), findsOneWidget);
    });

    testWidgets('displays time labels', (WidgetTester tester) async {
      final waveformData = List<double>.generate(100, (i) => 0.0);

      await tester.pumpWidget(
        TestApp(
          child: WaveformView(
            waveformData: waveformData,
            durationSec: 180.0,
            currentPositionSec: 90.5,
            isPlaying: false,
          ),
        ),
      );

      // Should show time like "1:30 / 3:00"
      expect(find.textContaining('/'), findsOneWidget);
    });

    testWidgets('play/pause button triggers callback', (WidgetTester tester) async {
      bool toggled = false;

      await tester.pumpWidget(
        TestApp(
          child: WaveformView(
            durationSec: 10.0,
            currentPositionSec: 0,
            isPlaying: false,
            onPlayPause: () => toggled = true,
          ),
        ),
      );

      await tester.tap(find.text('Play'));
      expect(toggled, isTrue);
    });

    testWidgets('stop button triggers callback', (WidgetTester tester) async {
      bool stopped = false;

      await tester.pumpWidget(
        TestApp(
          child: WaveformView(
            durationSec: 10.0,
            currentPositionSec: 0,
            isPlaying: false,
            onStop: () => stopped = true,
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.stop_rounded));
      expect(stopped, isTrue);
    });
  });
}

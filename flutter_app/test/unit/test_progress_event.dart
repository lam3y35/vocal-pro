// Tests for the ProgressEvent model in api_service.dart.

import 'package:flutter_test/flutter_test.dart';
import 'package:vocal_pro_flutter/services/api_service.dart';

void main() {
  group('ProgressEvent', () {
    test('parses progress type correctly', () {
      final event = ProgressEvent.fromJson({
        'type': 'progress',
        'percent': 50.0,
        'message': 'Processing...',
      });
      expect(event.type, ProgressType.progress);
      expect(event.percent, 50.0);
      expect(event.message, 'Processing...');
    });

    test('parses done type correctly', () {
      final event = ProgressEvent.fromJson({
        'type': 'done',
        'output_path': '/output/folder',
      });
      expect(event.type, ProgressType.done);
      expect(event.outputPath, '/output/folder');
    });

    test('parses error type correctly', () {
      final event = ProgressEvent.fromJson({
        'type': 'error',
        'message': 'Something went wrong',
      });
      expect(event.type, ProgressType.error);
      expect(event.message, 'Something went wrong');
    });

    test('parses cancelled type correctly', () {
      final event = ProgressEvent.fromJson({
        'type': 'cancelled',
      });
      expect(event.type, ProgressType.cancelled);
    });

    test('parses file_start type correctly', () {
      final event = ProgressEvent.fromJson({
        'type': 'file_start',
        'index': 0,
        'total': 3,
        'filename': 'song.mp3',
      });
      expect(event.type, ProgressType.fileStart);
      expect(event.index, 0);
      expect(event.total, 3);
      expect(event.filename, 'song.mp3');
    });

    test('parses pong type correctly', () {
      final event = ProgressEvent.fromJson({
        'type': 'pong',
      });
      expect(event.type, ProgressType.pong);
    });

    test('handles unknown type', () {
      final event = ProgressEvent.fromJson({
        'type': 'unknown_type',
      });
      expect(event.type, ProgressType.progress);  // defaults to progress
    });

    test('handles null values gracefully', () {
      final event = ProgressEvent.fromJson({
        'type': 'progress',
      });
      expect(event.percent, isNull);
      expect(event.message, isNull);
      expect(event.outputPath, isNull);
    });

    test('handles null type', () {
      final event = ProgressEvent.fromJson({});
      expect(event.type, ProgressType.progress);
    });

    test('handles int percent', () {
      final event = ProgressEvent.fromJson({
        'type': 'progress',
        'percent': 75,
        'message': '75%',
      });
      expect(event.percent, 75.0);
    });

    test('creates fully populated event', () {
      final event = ProgressEvent(
        type: ProgressType.fileStart,
        percent: 50.0,
        message: 'test',
        outputPath: '/out',
        index: 0,
        total: 5,
        filename: 'file.mp3',
      );
      expect(event.type, ProgressType.fileStart);
      expect(event.percent, 50.0);
      expect(event.message, 'test');
      expect(event.outputPath, '/out');
      expect(event.index, 0);
      expect(event.total, 5);
      expect(event.filename, 'file.mp3');
    });
  });

  group('ProgressType enum', () {
    test('has all expected values', () {
      expect(ProgressType.values.length, 6);
      expect(ProgressType.values, contains(ProgressType.progress));
      expect(ProgressType.values, contains(ProgressType.fileStart));
      expect(ProgressType.values, contains(ProgressType.done));
      expect(ProgressType.values, contains(ProgressType.error));
      expect(ProgressType.values, contains(ProgressType.cancelled));
      expect(ProgressType.values, contains(ProgressType.pong));
    });
  });
}

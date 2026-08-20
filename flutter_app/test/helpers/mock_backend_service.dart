// Mock BackendService for Flutter widget tests.
// Returns canned responses without spawning real processes.

import 'package:vocal_pro_flutter/services/backend_service.dart';

/// Mock backend service with controllable responses for testing.
class MockBackendService extends BackendService {
  MockBackendService() : super();

  bool _isRunning = true;
  int healthCallCount = 0;

  @override
  bool get isRunning => _isRunning;

  void setRunning(bool v) => _isRunning = v;

  @override
  Future<bool> start({
    Duration healthTimeout = const Duration(milliseconds: 500),
    Duration maxWait = const Duration(seconds: 40),
  }) async {
    return true;
  }

  @override
  Future<void> stop() async {}

  @override
  Future<Map<String, dynamic>> health() async {
    healthCallCount++;
    return {
      'status': 'ok',
      'gpu_available': false,
      'gpu_name': '',
      'gpu_vram': '',
    };
  }

  @override
  void setPythonPath(String path) {}

  @override
  String? get pythonPathOverride => null;

  @override
  void dispose() {}
}

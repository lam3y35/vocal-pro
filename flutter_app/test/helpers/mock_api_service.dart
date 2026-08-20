// Mock API service for Flutter widget tests.
// Returns canned responses without making real HTTP calls.

import 'dart:async';

import 'package:vocal_pro_flutter/services/api_service.dart';

/// Mock API service with configurable responses for testing.
class MockApiService extends ApiService {
  // Configurable responses
  final Map<String, dynamic> _healthResponse = {
    'status': 'ok',
    'gpu_available': false,
    'gpu_name': '',
    'gpu_vram': '',
  };

  final Map<String, dynamic> _configResponse = {
    'config': {
      'model_name': 'htdemucs_ft',
      'segment': 24.0,
      'overlap': 2.0,
      'shifts': 5,
      'output_format': 'wav',
      'enable_vocal_gate': true,
      'enable_spectral_denoise': true,
      'gate_threshold_db': -55.0,
      'gate_floor_db': -60.0,
      'denoise_strength': 0.65,
      'min_vocal_duration': 0.05,
      'safe_mode': false,
      'max_threads': 0,
      'audio_bitrate': '320k',
      'ffmpeg_path': '',
      'include_sfx': true,
      'save_background_track': false,
      'trim_silence': false,
      'enable_sfx_separation': true,
      'sfx_separation_margin_db': 5.0,
      'sfx_kernel_size': 15,
      'sfx_margin_harmonic_db': 3.0,
      'sfx_margin_percussive_db': 1.0,
    },
  };

  final Map<String, dynamic> _modelsResponse = {
    'models': {
      'htdemucs_ft': {
        'name': 'htdemucs_ft',
        'description': 'Best quality — fine-tuned',
        'recommended': true,
      },
      'htdemucs': {
        'name': 'htdemucs',
        'description': 'Faster — base transformer',
      },
      'mdx': {
        'name': 'mdx',
        'description': 'MDX winner',
      },
    },
  };

  final Map<String, dynamic> _outputsResponse = {
    'outputs': [
      {
        'name': 'test_song',
        'path': '/fake/output/test_song',
        'files': [
          {'name': 'vocals.wav', 'size_mb': 1.5, 'path': '/fake/output/test_song/vocals.wav'},
          {'name': 'drums.wav', 'size_mb': 2.0, 'path': '/fake/output/test_song/drums.wav'},
          {'name': 'bass.wav', 'size_mb': 1.2, 'path': '/fake/output/test_song/bass.wav'},
          {'name': 'other.wav', 'size_mb': 1.8, 'path': '/fake/output/test_song/other.wav'},
        ],
      },
    ],
  };

  final Map<String, dynamic> _stemsResponse = {
    'stems': [
      {'key': 'vocals', 'label': 'Vocals', 'filename': 'vocals.wav', 'path': '/fake/output/test_song/vocals.wav', 'size_mb': 1.5},
      {'key': 'drums', 'label': 'Drums', 'filename': 'drums.wav', 'path': '/fake/output/test_song/drums.wav', 'size_mb': 2.0},
      {'key': 'bass', 'label': 'Bass', 'filename': 'bass.wav', 'path': '/fake/output/test_song/bass.wav', 'size_mb': 1.2},
      {'key': 'other', 'label': 'Other', 'filename': 'other.wav', 'path': '/fake/output/test_song/other.wav', 'size_mb': 1.8},
    ],
  };

  final Map<String, dynamic> _historyResponse = {
    'history': [
      {
        'status': 'success',
        'files': ['song1.mp3', 'song2.mp3'],
        'model': 'htdemucs_ft',
        'timestamp': '2026-06-27 10:00:00',
        'output_folder': 'output_vocals/song1',
      },
    ],
  };

  final Map<String, dynamic> _downloadHistoryResponse = {
    'history': [
      {
        'status': 'success',
        'filename': 'test.mp3',
        'size': '5.2 MB',
        'timestamp': '2026-06-27 09:00:00',
        'url': 'https://example.com/test.mp3',
      },
    ],
  };

  final Map<String, dynamic> _uploadResponse = {
    'status': 'ok',
    'file_path': '/fake/uploads/test.wav',
    'filename': 'test.wav',
    'file_id': 'abc123',
    'size_mb': 2.5,
  };

  final Map<String, dynamic> _analyzeResponse = {
    'status': 'ok',
    'analysis': {
      'sample_rate': 44100,
      'duration_sec': 30.0,
      'bpm': 128.0,
      'key': 'C major',
      'waveform': List<double>.generate(100, (_) => 0.0),
      'waveform_samples': 100,
      'full_duration_sec': 180.0,
    },
  };

  final Map<String, dynamic> _separationResponse = {
    'status': 'started',
    'file_count': 1,
    'output_dir': '/fake/output',
  };

  final Map<String, dynamic> _statusResponse = {
    'is_running': false,
    'is_cancelled': false,
  };

  final Map<String, dynamic> _midiResponse = {
    'status': 'ok',
    'midi_path': '/fake/output/test_song/vocals.mid',
    'notes': 42,
    'filename': 'vocals.mid',
  };

  final Map<String, dynamic> _exportResponse = {
    'status': 'ok',
    'file_path': '/fake/output/test_song/stem_mix.wav',
    'filename': 'stem_mix.wav',
    'size_mb': 5.0,
  };

  final Map<String, dynamic> _exportSeparateResponse = {
    'status': 'ok',
    'files': [
      {'filename': 'vocals_custom.wav', 'size_mb': 1.5},
      {'filename': 'drums_custom.wav', 'size_mb': 2.0},
    ],
  };

  // Track calls
  int healthCallCount = 0;
  int configCallCount = 0;
  int uploadCallCount = 0;
  int separateCallCount = 0;
  int cancelCallCount = 0;
  int historyCallCount = 0;

  // Stream controller for WebSocket progress
  final _eventController = StreamController<ProgressEvent>.broadcast();

  @override
  Stream<ProgressEvent> get onProgress => _eventController.stream;

  /// Simulate a progress event
  void emitProgress(ProgressEvent event) {
    _eventController.add(event);
  }

  @override
  Future<Map<String, dynamic>> health() async {
    healthCallCount++;
    return Map<String, dynamic>.from(_healthResponse);
  }

  @override
  Future<Map<String, dynamic>> getConfig() async {
    configCallCount++;
    return Map<String, dynamic>.from(_configResponse);
  }

  @override
  Future<void> updateConfig(String key, dynamic value) async {
    _configResponse['config'][key] = value;
  }

  @override
  Future<Map<String, dynamic>> getModels() async {
    return Map<String, dynamic>.from(_modelsResponse);
  }

  @override
  Future<Map<String, dynamic>> uploadFile(String filePath) async {
    uploadCallCount++;
    return Map<String, dynamic>.from(_uploadResponse);
  }

  @override
  Future<Map<String, dynamic>> analyzeAudio(String filePath) async {
    return Map<String, dynamic>.from(_analyzeResponse);
  }

  @override
  Future<Map<String, dynamic>> startSeparation({
    required List<String> filePaths,
    String? outputDir,
    String modelName = 'htdemucs_ft',
    String outputFormat = 'wav',
    bool enableGate = true,
    bool enableDenoise = true,
    bool enableMultiband = true,
    bool enableProfile = true,
    bool adaptiveGate = true,
    bool trimSilence = false,
    bool karaokeMode = false,
    bool ensembleMode = false,
    bool includeSfx = true,
    bool saveBg = false,
    bool genSamples = true,
    bool enableSfxSep = true,
    double segment = 24.0,
    double overlap = 2.0,
    int shifts = 5,
    double gateThresholdDb = -55.0,
    double gateFloorDb = -60.0,
    double denoiseStrength = 0.65,
    double minVocalDuration = 0.05,
    String videoOutputMode = 'both',
    int parallelWorkers = 1,
  }) async {
    separateCallCount++;
    return Map<String, dynamic>.from(_separationResponse);
  }

  @override
  Future<void> cancelSeparation() async {
    cancelCallCount++;
  }

  @override
  Future<Map<String, dynamic>> getStatus() async {
    return Map<String, dynamic>.from(_statusResponse);
  }

  @override
  Future<Map<String, dynamic>> getHistory() async {
    historyCallCount++;
    return Map<String, dynamic>.from(_historyResponse);
  }

  @override
  Future<Map<String, dynamic>> getDownloadHistory() async {
    return Map<String, dynamic>.from(_downloadHistoryResponse);
  }

  @override
  Future<void> clearSepHistory() async {}

  @override
  Future<void> clearDownloadHistory() async {}

  @override
  Future<Map<String, dynamic>> getOutputs() async {
    return Map<String, dynamic>.from(_outputsResponse);
  }

  @override
  Future<Map<String, dynamic>> getStems(String folderName) async {
    return Map<String, dynamic>.from(_stemsResponse);
  }

  @override
  String getDownloadUrl(String folderName, String fileName) {
    return 'http://localhost:8000/api/outputs/$folderName/$fileName';
  }

  @override
  Future<List<int>> stemPreview({
    required String folderName,
    Map<String, double> volumes = const {},
    double masterVolume = 1.0,
  }) async {
    return [0x00, 0xFF, 0x00, 0xFF];  // fake WAV bytes
  }

  @override
  Future<Map<String, dynamic>> stemExport({
    required String folderName,
    Map<String, double> volumes = const {},
    double masterVolume = 1.0,
    String outputFormat = 'wav',
  }) async {
    return Map<String, dynamic>.from(_exportResponse);
  }

  @override
  Future<Map<String, dynamic>> stemExportSeparate({
    required String folderName,
    Map<String, double> volumes = const {},
    double masterVolume = 1.0,
    String outputFormat = 'wav',
  }) async {
    return Map<String, dynamic>.from(_exportSeparateResponse);
  }

  @override
  Future<Map<String, dynamic>> stemToMidi(String filePath) async {
    return Map<String, dynamic>.from(_midiResponse);
  }

  @override
  void connectWebSocket() {}

  @override
  void disconnectWebSocket() {}

  @override
  void dispose() {
    _eventController.close();
  }
}

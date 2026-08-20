/// Model for a separation job (one batch of files sent for separation).
/// Lightweight snapshot of job state, updated via WebSocket + polling.
class SeparationJob {
  final String jobId;
  final String status; // 'queued', 'running', 'completed', 'error', 'cancelled'
  final List<String> files;
  final Map<int, dynamic> progress; // index -> null, double, 'done', 'error', 'cancelled'
  final Map<int, String> outputPaths;
  final double totalProgress;
  final String statusText;
  final int currentFile;
  final int totalFiles;
  final String? currentFilename;
  final String? error;
  final DateTime createdAt;
  final DateTime? completedAt;
  final String? outputPath; // last output path

  SeparationJob({
    required this.jobId,
    required this.status,
    required this.files,
    this.progress = const {},
    this.outputPaths = const {},
    this.totalProgress = 0.0,
    this.statusText = '',
    this.currentFile = -1,
    this.totalFiles = 0,
    this.currentFilename,
    this.error,
    DateTime? createdAt,
    this.completedAt,
    this.outputPath,
  }) : createdAt = createdAt ?? DateTime.now();

  bool get isRunning => status == 'running' || status == 'queued';
  bool get isCompleted => status == 'completed';
  bool get isError => status == 'error';
  bool get isCancelled => status == 'cancelled';
  bool get isTerminal => isCompleted || isError || isCancelled;

  String get displayName {
    if (files.isEmpty) return jobId;
    if (files.length == 1) {
      final name = files.first.split(RegExp(r'[/\\]')).last;
      return name.length > 30 ? '${name.substring(0, 27)}...' : name;
    }
    final firstName = files.first.split(RegExp(r'[/\\]')).last;
    return '$firstName +${files.length - 1}';
  }

  /// Create from API JSON response.
  factory SeparationJob.fromJson(Map<String, dynamic> json) {
    final progressRaw = json['progress'] as Map<String, dynamic>? ?? {};
    final progress = <int, dynamic>{};
    for (final entry in progressRaw.entries) {
      final key = int.tryParse(entry.key);
      if (key != null) {
        progress[key] = entry.value;
      }
    }

    final outputPathsRaw = json['output_paths'] as Map<String, dynamic>? ?? {};
    final outputPaths = <int, String>{};
    for (final entry in outputPathsRaw.entries) {
      final key = int.tryParse(entry.key);
      if (key != null && entry.value is String) {
        outputPaths[key] = entry.value;
      }
    }

    return SeparationJob(
      jobId: json['job_id'] as String? ?? '',
      status: json['status'] as String? ?? 'unknown',
      files: (json['files'] as List<dynamic>?)?.cast<String>() ?? [],
      progress: progress,
      outputPaths: outputPaths,
      totalProgress: (json['total_progress'] as num?)?.toDouble() ?? 0.0,
      statusText: json['status_text'] as String? ?? '',
      currentFile: json['current_file'] as int? ?? -1,
      totalFiles: json['total_files'] as int? ?? 0,
      currentFilename: json['current_filename'] as String?,
      error: json['error'] as String?,
      completedAt: json['completed_at'] != null
          ? DateTime.fromMillisecondsSinceEpoch(
              (json['completed_at'] as num).toInt() * 1000)
          : null,
      outputPath: json['output_path'] as String?,
    );
  }
}

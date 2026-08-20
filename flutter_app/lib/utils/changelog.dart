import 'dart:io';

/// Version and changelog entry.
class _ChangelogEntry {
  final String version;
  final String date;
  final List<String> items;

  const _ChangelogEntry({
    required this.version,
    required this.date,
    required this.items,
  });
}

/// Changelog history — most recent first.
const _changelog = [
  _ChangelogEntry(
    version: '1.0.0',
    date: '2026-06-28',
    items: [
      'File associations — double-click audio/video files to open in VocalPro',
      'Always-on-top toggle to pin the app above other windows',
      'System tray — minimize to tray for background processing',
      'In-app notifications when separation completes',
      'Per-file progress indicators in the queue',
      'Auto-open output folder in Explorer when processing finishes',
      'Real waveform playback with actual audio output',
      'Persistent window position — remembers size and location',
      "What's New dialog showing release notes on first launch",
    ],
  ),
];

/// Current app version.
const String currentVersion = '1.0.0';

/// Check if this is a first launch (no version marker exists) or an upgrade
/// (stored version is older than [currentVersion]).
///
/// Returns `true` if the changelog dialog should be shown.
bool shouldShowChangelog() {
  final appData = _appDataDir();
  if (appData == null) return false;

  final marker = File('$appData/VocalPro/.version');
  if (!marker.existsSync()) return true;

  try {
    final stored = marker.readAsStringSync().trim();
    return stored != currentVersion;
  } catch (_) {
    return true;
  }
}

/// Record that the user has seen the current version's changelog.
void markChangelogSeen() {
  final appData = _appDataDir();
  if (appData == null) return;

  try {
    final dir = Directory('$appData/VocalPro');
    if (!dir.existsSync()) dir.createSync(recursive: true);
    File('$appData/VocalPro/.version').writeAsStringSync(currentVersion);
  } catch (_) {}
}

/// Get changelog entries for the current and recent versions.
List<String> getChangelogItems() {
  return _changelog
      .where((entry) => entry.version == currentVersion)
      .expand((entry) => entry.items)
      .toList();
}

String? _appDataDir() {
  return Platform.environment['APPDATA'] ??
      Platform.environment['USERPROFILE'] ??
      Platform.environment['HOME'];
}

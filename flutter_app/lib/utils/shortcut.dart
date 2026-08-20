import 'dart:io';

/// Creates a desktop shortcut (.lnk) for VocalPro on Windows.
///
/// Design mirrors the Python `create_desktop_shortcut()` in `code/_shared.py`:
/// - Writes a marker file to `%APPDATA%/VocalPro/.shortcut_created` so the
///   shortcut is only attempted once.
/// - If the shortcut already exists on the Desktop, just writes the marker
///   and returns without re-creating.
/// - Uses PowerShell's `WScript.Shell` COM object to create the shortcut.
/// - Sets the shortcut icon to `vocalpro.ico` (next to the EXE, if found),
///   falling back to the EXE's own embedded icon (index 0).
/// - Fails silently — this is a non-critical UX convenience.
///
/// Now async — file I/O no longer blocks the UI thread.
Future<void> createDesktopShortcut() async {
  final appData = Platform.environment['APPDATA'];
  final userProfile = Platform.environment['USERPROFILE'];
  final home = Platform.environment['HOME'];

  if (appData == null && userProfile == null && home == null) return;

  final vocalProDir = Directory(
    '${appData ?? '${userProfile!}/AppData/Roaming'}/VocalPro',
  );

  final marker = File('${vocalProDir.path}/.shortcut_created');
  if (await marker.exists()) return; // Already created once.

  // Desktop path: USERPROFILE/Desktop on Windows, ~/Desktop everywhere else.
  final desktopDir = userProfile != null
      ? '$userProfile\\Desktop'
      : '${home!}/Desktop';
  final shortcutPath = '$desktopDir\\VocalPro.lnk';
  final exePath = Platform.resolvedExecutable;
  final workingDir = Directory(exePath).parent.path;

  // Resolve the icon path:
  //   1. Look for vocalpro.ico next to the executable.
  //   2. If not found, point to the EXE itself (which has the icon embedded
  //      via Runner.rc → resources/app_icon.ico at build time).
  String iconPath = exePath;
  final iconCandidates = [
    '$workingDir\\vocalpro.ico',
    '$workingDir\\assets\\vocalpro.ico',
  ];
  for (final candidate in iconCandidates) {
    if (await File(candidate).exists()) {
      iconPath = candidate;
      break;
    }
  }

  // Ensure the app data directory exists so we can write the marker.
  try {
    await vocalProDir.create(recursive: true);
  } catch (_) {
    return;
  }

  // Shortcut exists already — just write the marker and return.
  if (await File(shortcutPath).exists()) {
    try {
      await marker.writeAsString('1');
    } catch (_) {}
    return;
  }

  // Create shortcut via PowerShell.
  try {
    final psScript = '''
\$wshell = New-Object -ComObject WScript.Shell
\$sc = \$wshell.CreateShortcut("$shortcutPath")
\$sc.TargetPath = "$exePath"
\$sc.WorkingDirectory = "$workingDir"
\$sc.Description = "VocalPro - AI Vocal Separation"
\$sc.IconLocation = "$iconPath,0"
\$sc.Save()
''';

    await Process.run(
      'powershell',
      [
        '-NoProfile',
        '-ExecutionPolicy',
        'Bypass',
        '-Command',
        psScript,
      ],
      runInShell: true,
    );

    await marker.writeAsString('1');
  } catch (_) {
    // Non-critical — fail silently.
  }
}

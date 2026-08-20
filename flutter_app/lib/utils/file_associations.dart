import 'dart:io';

/// Register VocalPro as the default handler for supported audio/media file
/// types (MP3, WAV, FLAC, OGG, MP4, MKV, AVI, MOV).
///
/// Uses PowerShell to write HKCU registry entries so no admin elevation is
/// needed. The user will be prompted to choose VocalPro on first open of
/// each extension (we set the ProgID but not the user-association override).
///
/// Runs once per app update — guarded by the same marker file pattern used
/// in [createDesktopShortcut].
///
/// Now async — file I/O no longer blocks the UI thread.
Future<void> registerFileAssociations() async {
  final appData = Platform.environment['APPDATA'];
  if (appData == null) return;

  final marker = File('$appData/VocalPro/.associations_registered');
  if (await marker.exists()) return;

  final exePath = Platform.resolvedExecutable;

  // Supported extensions + human-readable descriptions
  const exts = [
    ('.mp3', 'MP3 Audio'),
    ('.wav', 'WAV Audio'),
    ('.flac', 'FLAC Audio'),
    ('.ogg', 'OGG Audio'),
    ('.mp4', 'MP4 Video'),
    ('.mkv', 'MKV Video'),
    ('.avi', 'AVI Video'),
    ('.mov', 'MOV Video'),
  ];

  try {
    final psScript = StringBuffer();

    for (final (ext, desc) in exts) {
      final progId = 'VocalPro$ext';
      psScript.writeln('''
# Register ProgID $progId
New-Item -Path "HKCU:\\Software\\Classes\\$progId" -Force | Out-Null
New-ItemProperty -Path "HKCU:\\Software\\Classes\\$progId" -Name "(Default)" -Value "$desc" -PropertyType String -Force | Out-Null
New-Item -Path "HKCU:\\Software\\Classes\\$progId\\shell\\open\\command" -Force | Out-Null
New-ItemProperty -Path "HKCU:\\Software\\Classes\\$progId\\shell\\open\\command" -Name "(Default)" -Value '"$exePath" "%1"' -PropertyType String -Force | Out-Null
New-Item -Path "HKCU:\\Software\\Classes\\$progId\\DefaultIcon" -Force | Out-Null
New-ItemProperty -Path "HKCU:\\Software\\Classes\\$progId\\DefaultIcon" -Name "(Default)" -Value '"$exePath",0' -PropertyType String -Force | Out-Null
''');
    }

    // Register under HKCU\Software\Classes\.ext → VocalPro.ext
    // This sets the Open With suggestion without overriding the user's current
    // default, which requires admin elevation to change.
    for (final (ext, _) in exts) {
      psScript.writeln('''
New-ItemProperty -Path "HKCU:\\Software\\Classes\\$ext" -Name "(Default)" -Value "VocalPro$ext" -PropertyType String -Force | Out-Null
''');
    }

    await Process.run(
      'powershell',
      [
        '-NoProfile',
        '-ExecutionPolicy',
        'Bypass',
        '-Command',
        psScript.toString(),
      ],
      runInShell: true,
    );

    await marker.writeAsString('1');
  } catch (_) {
    // Non-critical — fail silently.
  }
}

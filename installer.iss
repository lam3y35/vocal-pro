; VocalPro - Inno Setup Installer Script
; Bundles the Flutter Windows EXE, icon, and Python API server
; with file association registration for audio/video formats.
;
; Compile with: ISCC installer.iss
; Or use build_dist.bat which auto-detects ISCC.

#define MyAppName "VocalPro"
#define MyAppVersion "2.5.0"
#define MyAppPublisher "VocalPro"
#define MyAppURL "https://codebuff.com"
#define MyAppExeName "vocal_pro_flutter.exe"

[Setup]
; Basic metadata
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Output
OutputDir=dist
OutputBaseFilename=VocalPro-Setup-{#MyAppVersion}
SetupIconFile=vocalpro.ico
Compression=lzma2/max
SolidCompression=yes
InternalCompressLevel=max

; Installation defaults
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
DisableReadyPage=yes

; Uninstall
UninstallDisplayIcon={app}\vocalpro.ico
UninstallDisplayName={#MyAppName}
CreateUninstallRegKey=yes

; Windows version range
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "fileassoc"; Description: "Register VocalPro as default player for audio/video files"; GroupDescription: "File associations:"; Flags: checkedonce

[Files]
; Main Flutter application
Source: "flutter_app\build\windows\x64\runner\Release\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "flutter_app\build\windows\x64\runner\Release\flutter_windows.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "flutter_app\build\windows\x64\runner\Release\native_assets.json"; DestDir: "{app}"; Flags: ignoreversion

; Flutter plugin DLLs
Source: "flutter_app\build\windows\x64\runner\Release\audioplayers_windows_plugin.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "flutter_app\build\windows\x64\runner\Release\desktop_drop_plugin.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "flutter_app\build\windows\x64\runner\Release\screen_retriever_windows_plugin.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "flutter_app\build\windows\x64\runner\Release\tray_manager_plugin.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "flutter_app\build\windows\x64\runner\Release\window_manager_plugin.dll"; DestDir: "{app}"; Flags: ignoreversion

; Data directory
Source: "flutter_app\build\windows\x64\runner\Release\data\*"; DestDir: "{app}\data"; Flags: ignoreversion recursesubdirs createallsubdirs

; Custom icon
Source: "vocalpro.ico"; DestDir: "{app}"; Flags: ignoreversion

; Python API server (required for the Flutter app's backend)
Source: "api_server\*"; DestDir: "{app}\api_server"; Flags: ignoreversion recursesubdirs createallsubdirs

; README
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Comment: "VocalPro - AI Vocal Separation"; IconFilename: "{app}\vocalpro.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon; Comment: "VocalPro - AI Vocal Separation"; IconFilename: "{app}\vocalpro.ico"

[Registry]
; File associations — only when task is selected
; Each extension gets a ProgID under HKCU (no admin needed) and an OpenWithProgID hint
; that points Explorer to VocalPro as a suggested handler.

#define FileExts "mp3 wav flac ogg mp4 mkv avi mov"
#define FileDescs "MP3 Audio|WAV Audio|FLAC Audio|OGG Audio|MP4 Video|MKV Video|AVI Video|MOV Video"

; .mp3
Root: HKCU; Subkey: "Software\Classes\VocalPro.mp3"; ValueType: string; ValueName: ""; ValueData: "MP3 Audio"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\VocalPro.mp3\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\vocalpro.ico,0"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\VocalPro.mp3\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.mp3"; ValueType: string; ValueName: ""; ValueData: "VocalPro.mp3"; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.mp3\OpenWithProgids"; ValueType: string; ValueName: "VocalPro.mp3"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc

; .wav
Root: HKCU; Subkey: "Software\Classes\VocalPro.wav"; ValueType: string; ValueName: ""; ValueData: "WAV Audio"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\VocalPro.wav\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\vocalpro.ico,0"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\VocalPro.wav\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.wav"; ValueType: string; ValueName: ""; ValueData: "VocalPro.wav"; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.wav\OpenWithProgids"; ValueType: string; ValueName: "VocalPro.wav"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc

; .flac
Root: HKCU; Subkey: "Software\Classes\VocalPro.flac"; ValueType: string; ValueName: ""; ValueData: "FLAC Audio"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\VocalPro.flac\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\vocalpro.ico,0"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\VocalPro.flac\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.flac"; ValueType: string; ValueName: ""; ValueData: "VocalPro.flac"; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.flac\OpenWithProgids"; ValueType: string; ValueName: "VocalPro.flac"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc

; .ogg
Root: HKCU; Subkey: "Software\Classes\VocalPro.ogg"; ValueType: string; ValueName: ""; ValueData: "OGG Audio"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\VocalPro.ogg\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\vocalpro.ico,0"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\VocalPro.ogg\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.ogg"; ValueType: string; ValueName: ""; ValueData: "VocalPro.ogg"; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.ogg\OpenWithProgids"; ValueType: string; ValueName: "VocalPro.ogg"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc

; .mp4
Root: HKCU; Subkey: "Software\Classes\VocalPro.mp4"; ValueType: string; ValueName: ""; ValueData: "MP4 Video"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\VocalPro.mp4\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\vocalpro.ico,0"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\VocalPro.mp4\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.mp4"; ValueType: string; ValueName: ""; ValueData: "VocalPro.mp4"; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.mp4\OpenWithProgids"; ValueType: string; ValueName: "VocalPro.mp4"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc

; .mkv
Root: HKCU; Subkey: "Software\Classes\VocalPro.mkv"; ValueType: string; ValueName: ""; ValueData: "MKV Video"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\VocalPro.mkv\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\vocalpro.ico,0"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\VocalPro.mkv\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.mkv"; ValueType: string; ValueName: ""; ValueData: "VocalPro.mkv"; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.mkv\OpenWithProgids"; ValueType: string; ValueName: "VocalPro.mkv"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc

; .avi
Root: HKCU; Subkey: "Software\Classes\VocalPro.avi"; ValueType: string; ValueName: ""; ValueData: "AVI Video"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\VocalPro.avi\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\vocalpro.ico,0"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\VocalPro.avi\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.avi"; ValueType: string; ValueName: ""; ValueData: "VocalPro.avi"; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.avi\OpenWithProgids"; ValueType: string; ValueName: "VocalPro.avi"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc

; .mov
Root: HKCU; Subkey: "Software\Classes\VocalPro.mov"; ValueType: string; ValueName: ""; ValueData: "MOV Video"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\VocalPro.mov\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\vocalpro.ico,0"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\VocalPro.mov\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.mov"; ValueType: string; ValueName: ""; ValueData: "VocalPro.mov"; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.mov\OpenWithProgids"; ValueType: string; ValueName: "VocalPro.mov"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc

[Run]
; Launch the app after install (optional)
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent runasoriginaluser; WorkingDir: "{app}"

[UninstallRun]
; Kill any running VocalPro processes before uninstalling
Filename: "{cmd}"; Parameters: "/C taskkill /f /im {#MyAppExeName} 2>nul"; Flags: runhidden

[Code]
// ── Prerequisite check: Python ─────────────────────────────────────────
// The Flutter app auto-launches a Python API server, so Python must be
// installed. We check at startup and warn if it's missing.
function IsPythonInstalled(): Boolean;
var
  ResultCode: Integer;
begin
  Result := False;
  if Exec('python', '--version', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    Result := (ResultCode = 0);
  if not Result then
    if Exec('python3', '--version', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      Result := (ResultCode = 0);
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  if not IsPythonInstalled then
  begin
    if MsgBox(
      'VocalPro requires Python 3.10 or later to run the API server backend.'#13#13
      'Would you like to continue with the installation anyway?'
      #13#13'You will need to install Python before running VocalPro.',
      mbConfirmation, MB_YESNO) = IDNO then
    begin
      Result := False;
    end;
  end;
end;

// ── Post-install: refresh shell icons ──────────────────────────────────
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Notify Explorer that file associations changed
    Exec('powershell', '-NoProfile -Command "& {''$app = New-Object -ComObject Shell.Application; $app.Windows() | foreach { $_.Refresh() }''}"',
      '', SW_HIDE, ewWaitUntilTerminated, 0);
  end;
end;

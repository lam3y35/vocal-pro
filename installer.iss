; VocalPro v3.0.0 — Turnkey All-in-One Inno Setup Installer Script
; Bundles:
; 1) Compiled Native Desktop Executable (Rust + Tauri v2)
; 2) Pre-packaged Embedded Python AI Worker (Torch + Demucs + DSP)
; 3) Pre-cached Offline Default Demucs AI Model (htdemucs)
; 4) Native Windows Shell Integration & File Associations

#define MyAppName "VocalPro"
#define MyAppVersion "3.0.0"
#define MyAppPublisher "VocalPro Studio"
#define MyAppURL "https://github.com/lam3y35/vocal-pro-rebuild"
#define MyAppExeName "vocalpro.exe"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

OutputDir=dist\installer
OutputBaseFilename=VocalPro-v{#MyAppVersion}-AllInOne-Setup
SetupIconFile=src-tauri\icons\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
InternalCompressLevel=max

DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
DisableReadyPage=yes

UninstallDisplayIcon={app}\vocalpro.ico
UninstallDisplayName={#MyAppName} v{#MyAppVersion}
CreateUninstallRegKey=yes
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce
Name: "fileassoc"; Description: "Register VocalPro as default stem separator for audio/video files"; GroupDescription: "File associations:"; Flags: checkedonce

[Files]
; 1. Compiled Native Desktop Core Binary
Source: "dist\bundle\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "src-tauri\icons\icon.ico"; DestDir: "{app}"; DestName: "vocalpro.ico"; Flags: ignoreversion

; 2. Embedded Python AI Engine & Dependencies
Source: "dist\bundle\engine\*"; DestDir: "{app}\engine"; Flags: ignoreversion recursesubdirs createallsubdirs

; 3. Python AI Worker Code
Source: "worker\vocalpro_worker\*"; DestDir: "{app}\worker\vocalpro_worker"; Flags: ignoreversion recursesubdirs createallsubdirs

; 4. Preloaded Offline AI Models
Source: "dist\bundle\models\*"; DestDir: "{localappdata}\VocalPro\models"; Flags: ignoreversion recursesubdirs createallsubdirs optional

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\vocalpro.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\vocalpro.ico"; Tasks: desktopicon

[Registry]
; Register VocalPro Media Handler
Root: HKCU; Subkey: "Software\Classes\VocalPro.MediaFile"; ValueType: string; ValueData: "VocalPro Audio/Video Media"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\VocalPro.MediaFile\DefaultIcon"; ValueType: string; ValueData: "{app}\vocalpro.ico"; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\VocalPro.MediaFile\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: fileassoc

; Associate standard audio & video extensions
Root: HKCU; Subkey: "Software\Classes\.mp3\OpenWithProgids"; ValueType: string; ValueName: "VocalPro.MediaFile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.wav\OpenWithProgids"; ValueType: string; ValueName: "VocalPro.MediaFile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.flac\OpenWithProgids"; ValueType: string; ValueName: "VocalPro.MediaFile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.ogg\OpenWithProgids"; ValueType: string; ValueName: "VocalPro.MediaFile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.m4a\OpenWithProgids"; ValueType: string; ValueName: "VocalPro.MediaFile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.mp4\OpenWithProgids"; ValueType: string; ValueName: "VocalPro.MediaFile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.mkv\OpenWithProgids"; ValueType: string; ValueName: "VocalPro.MediaFile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

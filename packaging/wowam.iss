#ifndef Version
  #define Version "0.0.0"
#endif

[Setup]
AppId={{8C0E0B6D-6F0B-4E7B-9C1C-5B1E7A2D4F10}
AppName=wowam
AppVersion={#Version}
AppVerName=wowam {#Version}
AppPublisher=wowam
AppPublisherURL=https://github.com/BilboTheGreedy/wowam
DefaultDirName={localappdata}\Programs\wowam
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=wowam-setup
SetupIconFile=..\build\wowam.ico
UninstallDisplayIcon={app}\wowam.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=force
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\wowam\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\wowam"; Filename: "{app}\wowam.exe"
Name: "{autodesktop}\wowam"; Filename: "{app}\wowam.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Classes\wago-app"; ValueType: string; ValueName: ""; ValueData: "URL:wago-app"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\wago-app"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\wago-app\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\wowam.exe"" ""%1"""

[Run]
Filename: "{app}\wowam.exe"; Description: "Start wowam"; Flags: nowait postinstall

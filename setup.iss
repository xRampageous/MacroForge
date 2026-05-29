; Inno Setup script for MacroForge
; Requires Inno Setup 6.x (free): https://jrsoftware.org/isdl.php

#define MyAppName "MacroForge"
#define MyAppVersion GetFileVersion('dist\MacroForge\MacroForge.exe')
#define MyAppPublisher "MacroForge"
#define MyAppURL ""
#define MyAppExeName "MacroForge.exe"

[Setup]
AppId={{MacroForge-Auto-Tool}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=installer
OutputBaseFilename=MacroForge-Setup
SetupIconFile=MacroForge.png
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\MacroForge\MacroForge.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\MacroForge\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs
Source: "MacroForge.png"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\MacroForge.png"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\MacroForge.png"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

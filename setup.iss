; Inno Setup script for MacroForge
; Requires Inno Setup 6.x (free): https://jrsoftware.org/isdl.php

#define MyAppName "MacroForge"
#ifndef MyAppVersion
#define MyAppVersion "1.0.0"
#endif
#define MyAppPublisher "MacroForge"
#define MyAppURL ""
#define MyAppExeName "MacroForge.exe"
#define MyAppSetupName "MacroForge-Setup-v" + MyAppVersion

[Setup]
AppId={{MacroForge-Auto-Tool}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=installer
OutputBaseFilename={#MyAppSetupName}
SetupIconFile=MacroForge.ico
UninstallDisplayIcon={app}\MacroForge.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\MacroForge\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\MacroForge.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\MacroForge.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[InstallDelete]
Type: files; Name: "{app}\MacroForge.update.exe"
Type: files; Name: "{app}\MacroForge.update.zip"
Type: files; Name: "{app}\MacroForge_update.bat"
Type: filesandordirs; Name: "{app}\MacroForge_update_tmp"
Type: filesandordirs; Name: "{app}\_internal.old"

[UninstallDelete]
Type: files; Name: "{app}\MacroForge.update.exe"
Type: files; Name: "{app}\MacroForge.update.zip"
Type: files; Name: "{app}\MacroForge_update.bat"
Type: filesandordirs; Name: "{app}\MacroForge_update_tmp"
Type: filesandordirs; Name: "{app}\_internal.old"

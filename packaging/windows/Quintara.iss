#define MyAppName "Quintara"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "AFWEF_147"
#define MyAppExeName "Quintara.exe"

[Setup]
AppId={{B5C7D734-2F46-4CFB-90C6-1234ABCD0001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Quintara
DefaultGroupName=Quintara
OutputDir=..\..\dist\installer
OutputBaseFilename=Quintara-{#MyAppVersion}-windows-x64
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "..\..\dist\Quintara.exe"; DestDir: "{app}"; DestName: "Quintara.exe"; Flags: ignoreversion

[Icons]
Name: "{group}\Quintara"; Filename: "{app}\{#MyAppExeName}"; Parameters: "gui"
Name: "{commondesktop}\Quintara"; Filename: "{app}\{#MyAppExeName}"; Parameters: "gui"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

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
ChangesAssociations=yes
CloseApplications=yes
RestartApplications=yes
SetupIconFile=..\..\src\quintara\assets\icons\quintara.ico
UninstallDisplayIcon={app}\Quintara.exe

[Files]
Source: "..\..\dist\Quintara.exe"; DestDir: "{app}"; DestName: "Quintara.exe"; Flags: ignoreversion
Source: "..\..\dist\quintara-cli.exe"; DestDir: "{app}"; DestName: "quintara-cli.exe"; Flags: ignoreversion

[Icons]
Name: "{group}\Quintara"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{commondesktop}\Quintara"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usUninstall then
  begin
    { Silent uninstall is the automation/default-preserve boundary.  Interactive
      uninstall keeps the explicit two-step confirmation for local data. }
    if UninstallSilent then
      Exit;
    DataDir := ExpandConstant('{localappdata}\Quintara');
    if DirExists(DataDir) and
       (MsgBox('是否同时删除 Quintara 的本地数据、模型和结果？默认选择“否”以便重新安装后继续使用。',
               mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES) then
      if MsgBox('此操作会永久删除本机 Quintara 研究数据。确认继续？',
                mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(DataDir, True, True, True);
  end;
end;

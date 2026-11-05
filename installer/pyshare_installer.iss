#define MyAppName "PyShare"
#define MyAppVersion "4.9.2"
#define MyAppPublisher "Pratik Pattanayak"
#define MyAppURL "https://github.com/pattanayakpratik/PyShare"
#define MyAppExeName "PyShare.exe"

[Setup]
AppId={{C8E64F77-9E4B-4E38-A68B-B0D4EE88D930}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=..\dist
OutputBaseFilename=PyShare-Setup-v{#MyAppVersion}
SetupIconFile=..\backend\app_icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\{#MyAppExeName}
VersionInfoVersion=4.9.2.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=PyShare - Local & P2P File Sharing Studio Installer
VersionInfoCopyright=Copyright (c) 2026 {#MyAppPublisher}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\backend\app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\backend\app_icon.png"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\app_icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// Prompt the user on uninstall to optionally delete sharing files and configuration
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DesktopFolder: String;
  UserProfile: String;
  ConfigFile: String;
  TempFilesDir: String;
begin
  if CurUninstallStep = usUninstall then
  begin
    if MsgBox('Do you want to delete your shared and received files folder (PyShare_Files on Desktop) and application configuration?', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
    begin
      DesktopFolder := ExpandConstant('{userdesktop}\PyShare_Files');
      if DirExists(DesktopFolder) then
      begin
        DelTree(DesktopFolder, True, True, True);
      end;

      UserProfile := ExpandConstant('{%USERPROFILE}');
      if UserProfile <> '' then
      begin
        ConfigFile := UserProfile + '\.pyshare_config.json';
        if FileExists(ConfigFile) then
          DeleteFile(ConfigFile);

        if DirExists(UserProfile + '\Desktop\PyShare_Files') then
          DelTree(UserProfile + '\Desktop\PyShare_Files', True, True, True);
      end;

      TempFilesDir := ExpandConstant('{tmp}\PyShare_Files');
      if DirExists(TempFilesDir) then
        DelTree(TempFilesDir, True, True, True);
    end;
  end;
end;

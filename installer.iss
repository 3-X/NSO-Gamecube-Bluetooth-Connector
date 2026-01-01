; Inno Setup Script for NSO GameCube Controller
; Download Inno Setup from: https://jrsoftware.org/isdl.php

#define MyAppName "NSO GameCube Controller"
#define MyAppVersion "1.0.0"
#define MyAppPublisher ""
#define MyAppExeName "NSO_GC_Controller.exe"

[Setup]
; NOTE: AppId uniquely identifies this application. Do not use the same AppId in different apps.
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; Output settings
OutputDir=installer_output
OutputBaseFilename=NSO_GC_Controller_Setup
SetupIconFile=
; Compression
Compression=lzma2
SolidCompression=yes
; Privileges - require admin for ViGEmBus check
PrivilegesRequired=admin
; Windows version
MinVersion=10.0
; UI
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Main executable (built by PyInstaller)
Source: "dist\NSO_GC_Controller.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Option to launch after install
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
const
  ViGEmBusURL = 'https://github.com/nefarius/ViGEmBus/releases/latest';

function IsViGEmBusInstalled(): Boolean;
var
  ResultCode: Integer;
begin
  // Check if ViGEmBus service exists
  Result := False;
  if Exec('cmd.exe', '/c sc query ViGEmBus | find "RUNNING"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    Result := (ResultCode = 0);

  // Also check if service exists but is stopped
  if not Result then
    if Exec('cmd.exe', '/c sc query ViGEmBus | find "STOPPED"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      Result := (ResultCode = 0);
end;

function InitializeSetup(): Boolean;
var
  ErrorCode: Integer;
begin
  Result := True;

  // Check for ViGEmBus
  if not IsViGEmBusInstalled() then
  begin
    if MsgBox('ViGEmBus driver is not installed!' + #13#10 + #13#10 +
              'This driver is REQUIRED for Xbox 360 controller emulation.' + #13#10 + #13#10 +
              'Would you like to download ViGEmBus now?' + #13#10 + #13#10 +
              'Click Yes to open the download page, then install ViGEmBus before continuing.' + #13#10 +
              'Click No to continue anyway (emulation will not work).',
              mbConfirmation, MB_YESNO) = IDYES then
    begin
      ShellExec('open', ViGEmBusURL, '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode);
      MsgBox('After installing ViGEmBus:' + #13#10 + #13#10 +
             '1. Restart your computer' + #13#10 +
             '2. Run this installer again' + #13#10 + #13#10 +
             'The installer will now exit.',
             mbInformation, MB_OK);
      Result := False;  // Cancel installation
    end;
  end;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  // Show reminder on ready page if ViGEmBus wasn't detected
  if CurPageID = wpReady then
  begin
    if not IsViGEmBusInstalled() then
    begin
      WizardForm.ReadyMemo.Lines.Add('');
      WizardForm.ReadyMemo.Lines.Add('WARNING: ViGEmBus driver was not detected.');
      WizardForm.ReadyMemo.Lines.Add('Xbox 360 emulation will not work until you install it.');
    end;
  end;
end;

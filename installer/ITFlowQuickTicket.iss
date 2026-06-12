; ITFlow Quick Ticket - Inno Setup installer
;
; Installs the tray app and prompts for per-install configuration
; (ITFlow base URL, API key, client ID, contact ID, priority), writing
; the result to %ProgramData%\ITFlowQuickTicket\config.json.
;
; Build:  ISCC.exe ITFlowQuickTicket.iss
; Output: installer\Output\ITFlowQuickTicketSetup.exe
;
; Supports unattended installs, e.g.:
;   ITFlowQuickTicketSetup.exe /VERYSILENT /SUPPRESSMSGBOXES ^
;     /ItflowBaseUrl=https://itflow.foleyit.com ^
;     /ApiKey=XXXXXXXX /ClientId=5 /ContactId=12 /Priority=Medium

#define MyAppName "ITFlow Quick Ticket"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Foley IT"
#define MyAppExeName "ITFlowQuickTicket.exe"

[Setup]
AppId={{B7B6A6E1-6E0C-4C2D-9F2F-7C1D4A9E3B21}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\ITFlowQuickTicket
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=ITFlowQuickTicketSetup
Compression=lzma
SolidCompression=yes
SetupIconFile=..\Windows\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "..\Windows\dist\ITFlowQuickTicket.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Start on login for all users
Name: "{commonstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
; Start menu shortcut (optional, useful for manually launching/testing)
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName} now"; Flags: nowait postinstall skipifsilent

[Code]
var
  ConfigPage: TInputQueryWizardPage;

procedure InitializeWizard;
begin
  ConfigPage := CreateInputQueryPage(wpSelectDir,
    'ITFlow Connection Settings',
    'Configure this install to talk to your ITFlow instance',
    'These values are saved to config.json and used by the tray app to ' +
    'submit tickets. You can find the API key under Admin > API Keys, ' +
    'and the Client ID on the client''s page in ITFlow.');

  ConfigPage.Add('ITFlow Base URL (e.g. https://itflow.example.com):', False);
  ConfigPage.Add('API Key:', False);
  ConfigPage.Add('Client ID:', False);
  ConfigPage.Add('Contact ID (optional):', False);
  ConfigPage.Add('Priority (Low / Medium / High / Critical):', False);

  ConfigPage.Values[0] := ExpandConstant('{param:ItflowBaseUrl|https://}');
  ConfigPage.Values[1] := ExpandConstant('{param:ApiKey|}');
  ConfigPage.Values[2] := ExpandConstant('{param:ClientId|}');
  ConfigPage.Values[3] := ExpandConstant('{param:ContactId|}');
  ConfigPage.Values[4] := ExpandConstant('{param:Priority|Medium}');
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;

  if CurPageID = ConfigPage.ID then
  begin
    if (Trim(ConfigPage.Values[0]) = '') or (Trim(ConfigPage.Values[0]) = 'https://') then
    begin
      MsgBox('Please enter the ITFlow base URL.', mbError, MB_OK);
      Result := False;
      exit;
    end;

    if Trim(ConfigPage.Values[1]) = '' then
    begin
      MsgBox('Please enter the API key.', mbError, MB_OK);
      Result := False;
      exit;
    end;

    if (Trim(ConfigPage.Values[2]) = '') or
       (StrToIntDef(Trim(ConfigPage.Values[2]), -1) < 0) then
    begin
      MsgBox('Please enter a valid numeric Client ID.', mbError, MB_OK);
      Result := False;
      exit;
    end;
  end;
end;

// Escapes a string for safe embedding in a JSON double-quoted string.
function JsonEscape(const S: String): String;
var
  R: String;
  I: Integer;
  C: Char;
begin
  R := '';
  for I := 1 to Length(S) do
  begin
    C := S[I];
    case C of
      '"':  R := R + '\"';
      '\':  R := R + '\\';
    else
      R := R + C;
    end;
  end;
  Result := R;
end;

procedure WriteConfigFile;
var
  BaseUrl, ApiKey, ClientId, ContactId, Priority: String;
  ContactJson: String;
  Json: String;
  ConfigDir, ConfigPath: String;
begin
  BaseUrl  := Trim(ConfigPage.Values[0]);
  ApiKey   := Trim(ConfigPage.Values[1]);
  ClientId := Trim(ConfigPage.Values[2]);
  ContactId := Trim(ConfigPage.Values[3]);
  Priority := Trim(ConfigPage.Values[4]);

  if Priority = '' then
    Priority := 'Medium';

  if ContactId = '' then
    ContactJson := 'null'
  else
    ContactJson := ContactId;

  Json := '{' + #13#10 +
    '    "itflow_base_url": "' + JsonEscape(BaseUrl) + '",' + #13#10 +
    '    "api_key": "' + JsonEscape(ApiKey) + '",' + #13#10 +
    '    "client_id": ' + ClientId + ',' + #13#10 +
    '    "contact_id": ' + ContactJson + ',' + #13#10 +
    '    "priority": "' + JsonEscape(Priority) + '"' + #13#10 +
    '}' + #13#10;

  ConfigDir := ExpandConstant('{commonappdata}\ITFlowQuickTicket');
  ConfigPath := ConfigDir + '\config.json';

  if not DirExists(ConfigDir) then
    ForceDirectories(ConfigDir);

  SaveStringToFile(ConfigPath, Json, False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    WriteConfigFile;
end;

; Inno Setup script for Fortnite AI Coach.
; Build: iscc /DAppVersion=0.5.0 packaging\installer.iss   (after PyInstaller has produced dist\FortniteAICoach)
; - Installs per user (no administrator rights) into %LOCALAPPDATA%\Programs\Fortnite AI Coach
; - Uninstall removes only the program. Your data (%APPDATA%\FortniteAICoach) and the Gemini key in
;   Windows Credential Manager are KEPT, so reinstalling or upgrading never loses your history.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppName "Fortnite AI Coach"
#define AppExe "FortniteAICoach.exe"
#define Root ".."

[Setup]
AppId={{6E2B7C1A-3F4D-4E8B-9A51-0C7D2F1B9E44}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Fortnite AI Coach (personal project)
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#Root}\dist\installer
OutputBaseFilename=FortniteAICoach-Setup-{#AppVersion}
SetupIconFile={#Root}\src\fortnite_coach\assets\app.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
ShowLanguageDialog=auto

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "hebrew"; MessagesFile: "compiler:Languages\Hebrew.isl"

[CustomMessages]
english.DataKept=Your data (%APPDATA%\FortniteAICoach) and your Gemini key were kept. Delete that folder and the "FortniteAICoach" entry in Windows Credential Manager to remove them.
hebrew.DataKept=הנתונים שלך (%APPDATA%\FortniteAICoach) ומפתח Gemini נשמרו. כדי להסיר אותם, מחק את התיקייה ואת הרשומה "FortniteAICoach" ב-Windows Credential Manager.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#Root}\dist\FortniteAICoach\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Root}\packaging\THIRD_PARTY_NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) then
    MsgBox(CustomMessage('DataKept'), mbInformation, MB_OK);
end;

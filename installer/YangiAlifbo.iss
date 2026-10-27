; Yangi Alifbo – Windows oʻrnatuvchi (Inno Setup 6).  CI: ISCC /DAppVersion=1.2.3 /DSourceDir=... installer\YangiAlifbo.iss
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist-portable\YangiAlifbo"
#endif

[Setup]
AppId={{8F6C1F8A-2C5B-4E0B-9C6E-7D2A1B3C4D5E}
AppName=Yangi Alifbo
AppVersion={#AppVersion}
AppVerName=Yangi Alifbo {#AppVersion}
AppPublisher=Yangi Alifbo
DefaultDirName={autopf}\Yangi Alifbo
DefaultGroupName=Yangi Alifbo
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=YangiAlifbo-Setup-{#AppVersion}
SetupIconFile=..\icon.ico
UninstallDisplayIcon={app}\YangiAlifbo.exe
UninstallDisplayName=Yangi Alifbo
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "autostart"; Description: "Windows bilan birga avtomatik ishga tushirish (tavsiya etiladi)"; GroupDescription: "Qoʻshimcha:"
Name: "desktopicon"; Description: "Ish stolida yorliq yaratish"; GroupDescription: "Qoʻshimcha:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Yangi Alifbo"; Filename: "{app}\YangiAlifbo.exe"
Name: "{group}\Yangi Alifbo – oʻchirish"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Yangi Alifbo"; Filename: "{app}\YangiAlifbo.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "YangiAlifbo"; ValueData: """{app}\YangiAlifbo.exe"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\YangiAlifbo.exe"; Description: "Yangi Alifbo ni hozir ishga tushirish"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /F /IM YangiAlifbo.exe"; Flags: runhidden; RunOnceId: "KillYangiAlifbo"

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

; Tanlangan til dasturga ham oʻtadi (pastda [Registry]: Software\Yangi Alifbo\Language);
; keyin uni Sozlamalar → Umumiy → Til da oʻzgartirish mumkin.  Tizim tiliga mosi avtomatik belgilanadi.
[Languages]
Name: "uz"; MessagesFile: "compiler:Default.isl,Uzbek.isl"
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Messages]
uz.SelectLanguageLabel=Oʻrnatish tilini tanlang. Dastur ham shu tilda ochiladi – keyin Sozlamalarda oʻzgartirish mumkin.
ru.SelectLanguageLabel=Выберите язык установки. Программа тоже будет на этом языке — его можно сменить в настройках.
en.SelectLanguageLabel=Select the language to use during the installation. The app will use it too – you can change it later in Settings.

[CustomMessages]
uz.TaskAutostart=Kompyuter yoqilganda avtomatik ishga tushsin (tavsiya etiladi)
ru.TaskAutostart=Запускать вместе с Windows (рекомендуется)
en.TaskAutostart=Start with Windows (recommended)
uz.TaskDesktop=Ish stolida yorliq yaratish
ru.TaskDesktop=Создать значок на рабочем столе
en.TaskDesktop=Create a desktop shortcut
uz.TaskGroup=Qoʻshimcha:
ru.TaskGroup=Дополнительно:
en.TaskGroup=Additional:
uz.RunNow=Yangi Alifbo ni hozir ishga tushirish
ru.RunNow=Запустить Yangi Alifbo сейчас
en.RunNow=Launch Yangi Alifbo now
uz.UninstallIcon=Yangi Alifbo – oʻchirish
ru.UninstallIcon=Удалить Yangi Alifbo
en.UninstallIcon=Uninstall Yangi Alifbo

[Tasks]
Name: "autostart"; Description: "{cm:TaskAutostart}"; GroupDescription: "{cm:TaskGroup}"
Name: "desktopicon"; Description: "{cm:TaskDesktop}"; GroupDescription: "{cm:TaskGroup}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; oldingi versiyalar oʻchirish yorligʻini doim oʻzbekcha nom bilan yaratgan
Type: files; Name: "{group}\Yangi Alifbo – oʻchirish.lnk"

[Icons]
Name: "{group}\Yangi Alifbo"; Filename: "{app}\YangiAlifbo.exe"
Name: "{group}\{cm:UninstallIcon}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Yangi Alifbo"; Filename: "{app}\YangiAlifbo.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Yangi Alifbo"; ValueType: string; ValueName: "Language"; ValueData: "{language}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "YangiAlifbo"; ValueData: """{app}\YangiAlifbo.exe"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\YangiAlifbo.exe"; Description: "{cm:RunNow}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /F /IM YangiAlifbo.exe"; Flags: runhidden; RunOnceId: "KillYangiAlifbo"

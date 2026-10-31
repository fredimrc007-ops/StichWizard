; Inno-Setup-Skript für StichWizard (wird von build_windows.sh gefüllt und übersetzt)
#define AppName "StichWizard"
#define AppVersion "@VERSION@"

[Setup]
AppId={{6F3B9A52-1C7E-4D8B-9E2A-5A7C3D1F0B42}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=StichWizard
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputBaseFilename=StichWizard-Setup-{#AppVersion}
SetupIconFile=stichwizard.ico
UninstallDisplayIcon={app}\stichwizard.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesAssociations=yes
MinVersion=10.0

[Languages]
Name: "de"; MessagesFile: "compiler:Languages\German.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "assoc"; Description: "StichWizard-Projekte (.stickproj) mit StichWizard öffnen"; GroupDescription: "Dateizuordnung:"

[Files]
Source: "python\*"; DestDir: "{app}\python"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "app\*"; DestDir: "{app}\app"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "stichwizard.ico"; DestDir: "{app}"
Source: "README.md"; DestDir: "{app}"

[InstallDelete]
; alte Programmdateien bei einem Update entfernen
Type: filesandordirs; Name: "{app}\app\stichwizard"
Type: filesandordirs; Name: "{app}\app\stickstudio"
Type: files; Name: "{app}\stickstudio.ico"

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\python\pythonw.exe"; Parameters: "-m stichwizard"; WorkingDir: "{app}"; IconFilename: "{app}\stichwizard.ico"; AppUserModelID: "StichWizard.StichWizard"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\python\pythonw.exe"; Parameters: "-m stichwizard"; WorkingDir: "{app}"; IconFilename: "{app}\stichwizard.ico"; AppUserModelID: "StichWizard.StichWizard"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\.stickproj"; ValueType: string; ValueData: "StichWizard.Projekt"; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\StichWizard.Projekt"; ValueType: string; ValueData: "StichWizard-Projekt"; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\StichWizard.Projekt\DefaultIcon"; ValueType: string; ValueData: "{app}\stichwizard.ico"; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\StichWizard.Projekt\shell\open\command"; ValueType: string; ValueData: """{app}\python\pythonw.exe"" -m stichwizard ""%1"""; Tasks: assoc

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: "-m stichwizard"; WorkingDir: "{app}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; zur Laufzeit entstandene Python-Cachedateien mit entfernen
Type: filesandordirs; Name: "{app}"

#define MyAppName "Ray Client"
#define MyAppVersion "2.1.0"
#define MyAppPublisher "Ray Client"
#define MyAppExeName "Ray Client.exe"

[Setup]
AppId={{A4D79A6C-7A0C-4A4C-9C35-2DCC78F02A31}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\Ray Client
DefaultGroupName=Ray Client
DisableProgramGroupPage=yes
OutputDir=..\release
OutputBaseFilename=Ray-Client-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesInstallIn64BitMode=x64
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\Ray Client.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Ray Client"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Ray Client"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Ray Client"; Flags: postinstall nowait skipifsilent

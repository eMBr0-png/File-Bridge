; File-Bridge installer script for Inno Setup
[Setup]
AppId={{YOUR-GUID-HERE}}
AppName=FileBridge
AppVersion=1.0
DefaultDirName={pf}\FileBridge
DefaultGroupName=FileBridge
DisableProgramGroupPage=no
OutputBaseFilename=FileBridgeSetup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\FileBridge"; Filename: "{app}\main.exe"
Name: "{group}\Uninstall FileBridge"; Filename: "{uninstallexe}"
Name: "{commondesktop}\FileBridge"; Filename: "{app}\main.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\main.exe"; Description: "Launch FileBridge"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

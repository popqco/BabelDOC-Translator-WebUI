[Setup]
AppName=BabelDOC 科技文档翻译器
AppVersion=1.0.0
AppPublisher=popqco
DefaultDirName={autopf}\BabelDOC-Translator
DefaultGroupName=BabelDOC
OutputDir=dist
OutputBaseFilename=BabelDOC_Translator_Setup_v1.0
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
DisableProgramGroupPage=yes

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "venv\*,data\config.json,dist\*,__pycache__\*"

[Icons]
Name: "{autoprograms}\BabelDOC 科技文档翻译器"; Filename: "{app}\run.bat"
Name: "{autodesktop}\BabelDOC 科技文档翻译器"; Filename: "{app}\run.bat"; Tasks: desktopicon

[Run]
Filename: "{app}\run.bat"; Description: "{cm:LaunchProgram,BabelDOC 科技文档翻译器}"; Flags: shellexec postinstall nowait skipifsilent

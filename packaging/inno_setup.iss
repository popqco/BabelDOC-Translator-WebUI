; BabelDOC 科技文档翻译器 — Inno Setup 打包脚本
; 打包命令（在 packaging/ 目录下执行）:
;   iscc inno_setup.iss
; 产物位于 ../dist/

[Setup]
; 固定 AppId：升级/卸载识别的唯一标识，重命名应用也不会导致安装身份漂移
AppId={{7C1E5D8B-9A42-4F6E-B3D1-A26C8F0E5B94}}
AppName=BabelDOC 科技文档翻译器
AppVersion=1.0.0
VersionInfoVersion=1.0.0
VersionInfoCompany=popqco
VersionInfoDescription=BabelDOC 科技文档/芯片规格书批量双语翻译器 (桌面版)
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
UninstallDisplayIcon={sys}\wscript.exe

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; venv 由 install.bat 在目标机自举生成，故不打入安装包；
; data/ 为运行时用户数据（含 API Key），outputs/ video_frames/ dist/ .git/
; 及各层 __pycache__ 均为非发布内容，一并排除（裸目录名可匹配任意层级）
Source: "..\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: ".git,__pycache__,data,outputs,video_frames,dist,tests,.zcode,*.pyc,*.pyo"

[Icons]
; 静默启动器（无控制台窗口）；venv 缺失时会弹出引导提示
Name: "{autoprograms}\BabelDOC 科技文档翻译器"; Filename: "{app}\start_silent.vbs"; WorkingDir: "{app}"
Name: "{autodesktop}\BabelDOC 科技文档翻译器"; Filename: "{app}\start_silent.vbs"; Tasks: desktopicon; WorkingDir: "{app}"

[Run]
; 首次安装必须先初始化 Python 运行环境（需要 Python 3.10~3.13 与网络），
; 因此默认勾选安装环境；启动入口留给环境就绪后的用户自行触发
Filename: "{app}\install.bat"; Description: "初始化运行环境（需要 Python 3.10~3.13 与网络，推荐勾选）"; Flags: shellexec postinstall skipifsilent
Filename: "{app}\start_silent.vbs"; Description: "{cm:LaunchProgram,BabelDOC 科技文档翻译器}"; Flags: shellexec postinstall nowait skipifsilent unchecked

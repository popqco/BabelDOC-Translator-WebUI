@echo off
chcp 65001 >nul
title BabelDOC 科技文档/芯片规格书翻译器 WebUI
echo ============================================================
echo   正在启动 BabelDOC 高质量双语翻译服务...
echo   启动成功后请在浏览器访问: http://localhost:7860
echo ============================================================

if not exist venv (
    echo [提示] 检测到尚未初始化环境，正在自动执行安装...
    call install.bat
)

call venv\Scripts\activate.bat
python app.py
pause

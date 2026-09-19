@echo off
chcp 65001 >nul
title BabelDOC 翻译器 - 控制台调试模式
cd /d "%~dp0"

if not exist venv\Scripts\python.exe (
    echo [提示] 未找到 venv，请先运行 install.bat。
    pause
    exit /b 1
)

echo 正在以调试模式启动（会显示日志窗口，日常使用请双击 start_silent.vbs）...
venv\Scripts\python.exe app.py
pause
